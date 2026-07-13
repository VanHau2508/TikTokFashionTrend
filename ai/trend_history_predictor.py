import argparse
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import joblib
import numpy as np
import tensorflow as tf

from database.config import SessionLocal
from database.models import Hashtag, TrendHistory, Prediction
from ai.tag_filters import BLACKLIST_TAGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TrendHistoryPredictor:
    """
    LSTM Predictor V3.

    Hướng V3:
    - Hashtag = Trend
    - Input: trend_history sequence theo từng hashtag
    - Features lấy từ config v3
    - Target: next view_growth
    - Transform lúc predict phải giống lúc train:
        + log1p: view_growth, like_growth, video_count
        + none: engagement_rate
    - Target inverse: target_scaler inverse -> expm1
    - Chỉ dự đoán khi hashtag đủ dữ liệu lịch sử đáng tin cậy
    - Lưu kết quả vào predictions bằng hashtag_id
    """

    def __init__(self, model_dir="ai/models/lstm_trend_history_v3"):
        self.model_dir = model_dir

        self.model_path = os.path.join(
            model_dir,
            "lstm_trend_history_growth_model_v3.keras"
        )

        # Fallback nếu bạn vẫn còn file .h5 cũ
        if not os.path.exists(self.model_path):
            fallback_h5 = os.path.join(
                model_dir,
                "lstm_trend_history_growth_model_v3.h5"
            )
            if os.path.exists(fallback_h5):
                self.model_path = fallback_h5

        self.feature_scaler_path = os.path.join(
            model_dir,
            "trend_history_feature_scaler_v3.pkl"
        )
        self.target_scaler_path = os.path.join(
            model_dir,
            "trend_history_target_scaler_v3.pkl"
        )
        self.config_path = os.path.join(
            model_dir,
            "lstm_trend_history_growth_config_v3.json"
        )

        logger.info("🔮 Đang load LSTM Trend History model V3...")

        self._validate_model_files()

        self.model = tf.keras.models.load_model(
            self.model_path,
            compile=False
        )

        self.feature_scaler = joblib.load(self.feature_scaler_path)
        self.target_scaler = joblib.load(self.target_scaler_path)

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.features = self.config["features"]
        self.seq_length = int(self.config["seq_length"])
        self.model_version = self.config.get(
            "model_version",
            "lstm_trend_history_growth_v3"
        )

        # Cell 6 training v3 đang chỉ log một số feature.
        # Nếu config có log_features thì dùng config; nếu không có thì fallback theo v3.
        self.log_features = set(
            self.config.get(
                "log_features",
                ["view_growth", "like_growth", "video_count"]
            )
        )

        data_quality_rule = self.config.get("data_quality_rule", {})
        self.max_imputed_ratio_in_window = float(
            data_quality_rule.get("max_imputed_ratio_in_window", 0.5)
        )
        self.min_avg_video_count = float(
            data_quality_rule.get("min_avg_video_count", 1.0)
        )

        logger.info("✅ Load model V3 thành công")
        logger.info(f"📌 Model path: {self.model_path}")
        logger.info(f"📌 Model version: {self.model_version}")
        logger.info(f"📌 Features: {self.features}")
        logger.info(f"📌 Log features: {sorted(list(self.log_features))}")
        logger.info(f"📌 Sequence length: {self.seq_length}")

    def _validate_model_files(self):
        required_paths = [
            self.model_path,
            self.feature_scaler_path,
            self.target_scaler_path,
            self.config_path,
        ]

        missing = [path for path in required_paths if not os.path.exists(path)]

        if missing:
            raise FileNotFoundError(
                "Thiếu file model/scaler/config LSTM v3:\n"
                + "\n".join(missing)
                + "\nHãy đặt đủ 4 file vào ai/models/lstm_trend_history_v3/"
            )

    def _deduplicate_history_by_date(self, history_rows):
        """
        Phòng trường hợp trend_history bị trùng hashtag_id + date.
        Nếu trùng, giữ dòng cuối cùng theo date.
        """
        date_map = {}

        for row in history_rows:
            date_map[row.date] = row

        return [
            date_map[date]
            for date in sorted(date_map.keys())
        ]

    def _parse_prediction_base_date(self, prediction_base_date):
        """
        Chuẩn hóa ngày chốt dữ liệu dùng để dự đoán.
        Nếu prediction_base_date = "2026-06-11" thì chỉ dùng dữ liệu <= ngày này.
        Nếu không truyền, dùng ngày mới nhất của từng hashtag.
        """
        if prediction_base_date in [None, "", 0, "0"]:
            return None

        if isinstance(prediction_base_date, str):
            return datetime.strptime(prediction_base_date, "%Y-%m-%d").date()

        return prediction_base_date

    def _is_consecutive_rows(self, rows):
        if len(rows) <= 1:
            return True

        dates = [row.date for row in rows]

        for index in range(1, len(dates)):
            if (dates[index] - dates[index - 1]).days != 1:
                return False

        return True

    def _check_prediction_eligibility(self, recent_rows):
        """
        Không ép LSTM dự đoán nếu dữ liệu không đủ chuẩn.
        Điều này giúp tránh prediction ảo cho hashtag mới hoặc chuỗi bị đứt ngày.
        """
        if len(recent_rows) < self.seq_length:
            return False, "insufficient_history"

        if not self._is_consecutive_rows(recent_rows):
            return False, "non_consecutive_history"

        imputed_count = sum(
            1 for row in recent_rows
            if bool(getattr(row, "is_imputed", False))
        )
        imputed_ratio = imputed_count / max(1, len(recent_rows))

        if imputed_ratio > self.max_imputed_ratio_in_window:
            return False, "too_many_imputed_rows"

        avg_video_count = np.mean([
            float(getattr(row, "video_count", 0) or 0)
            for row in recent_rows
        ])

        if avg_video_count < self.min_avg_video_count:
            return False, "too_low_video_count"

        return True, "eligible"

    def _transform_feature_matrix(self, feature_data):
        """
        Transform phải giống Cell 6 khi training v3:
        - log1p: view_growth, like_growth, video_count
        - none: engagement_rate
        """
        feature_data = np.array(feature_data, dtype=float)
        feature_data = np.clip(feature_data, 0, None)

        transformed = feature_data.copy()

        for idx, feature in enumerate(self.features):
            if feature in self.log_features:
                transformed[:, idx] = np.log1p(transformed[:, idx])

        return transformed

    def predict_one_hashtag(self, history_rows):
        """
        history_rows: danh sách TrendHistory của 1 hashtag, sort theo date tăng dần.
        Return:
        - predicted_growth nếu predict được
        - None nếu không đủ điều kiện
        """
        history_rows = self._deduplicate_history_by_date(history_rows)

        if len(history_rows) < self.seq_length:
            return None, "insufficient_history"

        recent_rows = history_rows[-self.seq_length:]

        eligible, reason = self._check_prediction_eligibility(recent_rows)
        if not eligible:
            return None, reason

        feature_data = []

        for row in recent_rows:
            feature_data.append([
                float(getattr(row, feature, 0) or 0)
                for feature in self.features
            ])

        transformed_features = self._transform_feature_matrix(feature_data)
        scaled_features = self.feature_scaler.transform(transformed_features)

        X = scaled_features.reshape(
            1,
            self.seq_length,
            len(self.features)
        )

        pred_scaled = self.model.predict(X, verbose=0)

        # Target lúc train vẫn log1p(view_growth), nên inverse xong expm1.
        pred_log = self.target_scaler.inverse_transform(pred_scaled)[0][0]
        predicted_growth = np.expm1(pred_log)

        if not np.isfinite(predicted_growth):
            return None, "non_finite_prediction"

        return max(0, float(predicted_growth)), "success"

    def run_batch_prediction(
        self,
        limit=None,
        should_stop=None,
        prediction_base_date=None,
        dry_run=False,
        overwrite_evaluated=False,
    ):
        db = SessionLocal()

        def stop_requested():
            return should_stop is not None and should_stop()

        try:
            base_date = self._parse_prediction_base_date(prediction_base_date)

            query = db.query(Hashtag)

            if limit:
                query = query.limit(limit)

            hashtags = query.all()

            saved_count = 0
            created_count = 0
            updated_count = 0
            skipped_count = 0
            skipped_evaluated_count = 0

            logger.info("=" * 80)
            logger.info("🚀 RUN LSTM TREND HISTORY PREDICTION V3")
            logger.info(f"📌 Limit: {limit or 'all'}")
            logger.info(f"📌 Dry run: {dry_run}")
            logger.info(f"📌 Overwrite evaluated predictions: {overwrite_evaluated}")
            logger.info(
                "📌 Prediction base date: "
                f"{base_date or 'latest history date per hashtag'}"
            )
            logger.info("=" * 80)

            for hashtag in hashtags:
                if stop_requested():
                    logger.warning("🛑 LSTM prediction đã bị dừng bởi admin.")
                    return {
                        "status": "cancelled",
                        "saved_count": saved_count,
                        "skipped_count": skipped_count,
                        "model_version": self.model_version,
                        "prediction_base_date": str(base_date) if base_date else None,
                        "message": "Task đã được dừng bởi admin."
                    }

                tag_name = (hashtag.tag_name or "").lower().strip()

                if tag_name in BLACKLIST_TAGS:
                    skipped_count += 1
                    continue

                history_query = (
                    db.query(TrendHistory)
                    .filter(TrendHistory.hashtag_id == hashtag.hashtag_id)
                )

                if base_date:
                    history_query = history_query.filter(
                        TrendHistory.date <= base_date
                    )

                history_rows = (
                    history_query
                    .order_by(TrendHistory.date.asc())
                    .all()
                )

                history_rows = self._deduplicate_history_by_date(history_rows)

                if len(history_rows) < self.seq_length:
                    skipped_count += 1
                    continue

                latest_history = history_rows[-1]
                prediction_date = latest_history.date
                predicted_for_date = prediction_date + timedelta(days=1)

                predicted_growth, predict_status = self.predict_one_hashtag(history_rows)

                if predicted_growth is None:
                    skipped_count += 1
                    logger.info(f"⏭️ #{hashtag.tag_name}: skip={predict_status}")
                    continue

                predicted_next_views = (
                    float(latest_history.view_count or 0) + predicted_growth
                )

                if not dry_run:
                    existing_prediction = (
                        db.query(Prediction)
                        .filter(
                            Prediction.hashtag_id == hashtag.hashtag_id,
                            Prediction.prediction_date == prediction_date,
                            Prediction.predicted_for_date == predicted_for_date,
                            Prediction.prediction_type == "view_growth",
                            Prediction.model_version == self.model_version
                        )
                        .first()
                    )

                    if existing_prediction:
                        # SAFE RULE:
                        # Nếu prediction đã được evaluator chấm rồi thì KHÔNG ghi đè mặc định.
                        # Tránh việc chạy lại predictor làm mất actual_value/accuracy_score lịch sử.
                        if (
                            existing_prediction.actual_value is not None
                            and not overwrite_evaluated
                        ):
                            skipped_count += 1
                            skipped_evaluated_count += 1
                            logger.info(
                                f"⏭️ #{hashtag.tag_name}: prediction đã được đánh giá, bỏ qua | "
                                f"prediction_date={prediction_date}, "
                                f"predicted_for_date={predicted_for_date}"
                            )
                            continue

                        existing_prediction.predicted_value = predicted_growth
                        existing_prediction.created_at = datetime.now(timezone.utc)

                        # Chỉ reset actual/accuracy khi chủ động bật overwrite_evaluated.
                        # Với prediction đang chờ, hai trường này vốn đang None nên không ảnh hưởng.
                        if overwrite_evaluated:
                            existing_prediction.actual_value = None
                            existing_prediction.accuracy_score = None

                        updated_count += 1
                    else:
                        prediction = Prediction(
                            trend_id=None,
                            hashtag_id=hashtag.hashtag_id,
                            prediction_type="view_growth",
                            prediction_date=prediction_date,
                            predicted_for_date=predicted_for_date,
                            predicted_value=predicted_growth,
                            actual_value=None,
                            accuracy_score=None,
                            model_version=self.model_version
                        )

                        db.add(prediction)
                        created_count += 1

                    db.commit()

                saved_count += 1

                logger.info(
                    f"✅ #{hashtag.tag_name}: "
                    f"prediction_date={prediction_date}, "
                    f"predicted_for_date={predicted_for_date}, "
                    f"predicted_growth={predicted_growth:,.0f}, "
                    f"predicted_next_views≈{predicted_next_views:,.0f}"
                )

            logger.info("=" * 80)
            logger.info("🏁 Batch prediction V3 completed")
            logger.info(f"✅ Saved/updated: {saved_count}")
            logger.info(f"   ├─ Created: {created_count}")
            logger.info(f"   └─ Updated waiting/allowed: {updated_count}")
            logger.info(f"⏭️ Skipped: {skipped_count}")
            logger.info(f"   └─ Skipped evaluated predictions: {skipped_evaluated_count}")
            logger.info(f"📌 Model version: {self.model_version}")
            logger.info(
                "📌 Prediction base date: "
                f"{base_date or 'latest history date per hashtag'}"
            )
            logger.info("=" * 80)

            return {
                "status": "completed",
                "saved_count": saved_count,
                "created_count": created_count,
                "updated_count": updated_count,
                "skipped_count": skipped_count,
                "skipped_evaluated_count": skipped_evaluated_count,
                "model_version": self.model_version,
                "prediction_base_date": str(base_date) if base_date else None,
                "dry_run": dry_run,
                "message": "LSTM prediction V3 completed."
            }

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Lỗi khi dự đoán: {e}")
            raise e

        finally:
            db.close()


def _build_arg_parser():
    parser = argparse.ArgumentParser(description="Run LSTM trend prediction V3 safely")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số hashtag cần quét")
    parser.add_argument("--base-date", default=None, help="YYYY-MM-DD. Chốt dữ liệu dự đoán đến ngày này")
    parser.add_argument("--dry-run", action="store_true", help="Chạy thử, không ghi DB")
    parser.add_argument(
        "--overwrite-evaluated",
        action="store_true",
        help="Cho phép ghi đè prediction đã được đánh giá. Không khuyến nghị dùng hằng ngày.",
    )
    return parser


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    predictor = TrendHistoryPredictor()
    predictor.run_batch_prediction(
        limit=args.limit,
        prediction_base_date=args.base_date,
        dry_run=args.dry_run,
        overwrite_evaluated=args.overwrite_evaluated,
    )
