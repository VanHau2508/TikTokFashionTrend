import argparse
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from math import sqrt
import pandas as pd
import joblib
import numpy as np
from tensorflow.keras.models import load_model

from database.config import SessionLocal
from database.models import TrendHistory, Prediction


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


FEATURES = ["view_growth", "like_growth", "engagement_rate", "video_count"]
TARGET = "view_growth"

SEQ_LENGTH = 4

DEFAULT_MODEL_DIR = Path("ai/models/lstm_trend_history_v3")
DEFAULT_MODEL_VERSION = "lstm_v3_bt_20260601_20260611"
DEFAULT_PREDICTION_TYPE = "bt_view_growth"


class LSTMBacktester:
    def __init__(
        self,
        model_dir=DEFAULT_MODEL_DIR,
        model_version=DEFAULT_MODEL_VERSION,
        prediction_type=DEFAULT_PREDICTION_TYPE,
    ):
        self.db = SessionLocal()

        self.model_dir = Path(model_dir)
        self.model_version = model_version
        self.prediction_type = prediction_type

        self.model_path = self.model_dir / "lstm_trend_history_growth_model_v3.keras"
        self.feature_scaler_path = self.model_dir / "trend_history_feature_scaler_v3.pkl"
        self.target_scaler_path = self.model_dir / "trend_history_target_scaler_v3.pkl"
        self.config_path = self.model_dir / "lstm_trend_history_growth_config_v3.json"

        self.model = None
        self.feature_scaler = None
        self.target_scaler = None
        self.config = {}

    def close(self):
        try:
            self.db.close()
        except Exception:
            pass

    def load_artifacts(self):
        if not self.model_path.exists():
            raise FileNotFoundError(f"Không tìm thấy model: {self.model_path}")

        if not self.feature_scaler_path.exists():
            raise FileNotFoundError(f"Không tìm thấy feature scaler: {self.feature_scaler_path}")

        if not self.target_scaler_path.exists():
            raise FileNotFoundError(f"Không tìm thấy target scaler: {self.target_scaler_path}")

        if not self.config_path.exists():
            raise FileNotFoundError(f"Không tìm thấy config: {self.config_path}")

        logger.info(f"📦 Loading model: {self.model_path}")
        self.model = load_model(self.model_path)

        logger.info(f"📦 Loading feature scaler: {self.feature_scaler_path}")
        self.feature_scaler = joblib.load(self.feature_scaler_path)

        logger.info(f"📦 Loading target scaler: {self.target_scaler_path}")
        self.target_scaler = joblib.load(self.target_scaler_path)

        logger.info(f"📦 Loading config: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as file:
            self.config = json.load(file)

        logger.info("✅ Loaded LSTM v3 artifacts successfully.")

    def get_log_features(self):
        return self.config.get(
            "log_features",
            ["view_growth", "like_growth", "video_count"],
        )

    def transform_feature_value(self, feature_name, value):
        value = float(value or 0)

        if feature_name in self.get_log_features():
            value = max(0, value)
            return np.log1p(value)

        return value

    def inverse_target_value(self, scaled_prediction):
        """
        Model output nằm trong không gian target_scaler.
        target_scaler.inverse_transform -> log1p(view_growth).
        Sau đó expm1 -> view_growth gốc.
        """

        scaled_prediction = np.array([[float(scaled_prediction)]])
        target_log_value = self.target_scaler.inverse_transform(scaled_prediction)[0][0]

        predicted_value = np.expm1(target_log_value)
        predicted_value = max(0, predicted_value)

        return float(predicted_value)

    def calculate_accuracy(self, predicted_value, actual_value):
        predicted = float(predicted_value or 0)
        actual = float(actual_value or 0)

        if predicted == 0 and actual == 0:
            return 1.0

        error_rate = abs(predicted - actual) / (abs(actual) + 1)
        accuracy = max(0, 1 - error_rate)

        return round(accuracy, 4)

    def make_date_range(self, start_date, end_date):
        dates = []

        current = start_date

        while current <= end_date:
            dates.append(current)
            current += timedelta(days=1)

        return dates

    def load_history_rows(self, warmup_start_date, end_date, limit_hashtags=None):
        query = (
            self.db.query(TrendHistory)
            .filter(TrendHistory.date >= warmup_start_date)
            .filter(TrendHistory.date <= end_date)
            .order_by(TrendHistory.hashtag_id.asc(), TrendHistory.date.asc())
        )

        rows = query.all()

        history_by_hashtag = {}

        for row in rows:
            if limit_hashtags is not None and len(history_by_hashtag) >= limit_hashtags:
                if row.hashtag_id not in history_by_hashtag:
                    continue

            history_by_hashtag.setdefault(row.hashtag_id, {})
            history_by_hashtag[row.hashtag_id][row.date] = row

        return history_by_hashtag

    def build_input_sequence(self, window_rows):
        feature_matrix = []

        for row in window_rows:
            feature_row = []

            for feature_name in FEATURES:
                value = getattr(row, feature_name, 0)
                feature_row.append(
                    self.transform_feature_value(feature_name, value)
                )

            feature_matrix.append(feature_row)

        feature_df = pd.DataFrame(feature_matrix, columns=FEATURES)

        scaled_matrix = self.feature_scaler.transform(feature_df)

        return scaled_matrix.reshape(1, SEQ_LENGTH, len(FEATURES))

    def predict_one(self, window_rows):
        x = self.build_input_sequence(window_rows)
        scaled_prediction = self.model.predict(x, verbose=0)[0][0]
        predicted_value = self.inverse_target_value(scaled_prediction)

        return predicted_value

    def clean_old_backtest_results(self):
        deleted = (
            self.db.query(Prediction)
            .filter(Prediction.model_version == self.model_version)
            .filter(Prediction.prediction_type == self.prediction_type)
            .delete(synchronize_session=False)
        )

        self.db.commit()

        logger.info(
            f"🧹 Đã xóa {deleted} dòng backtest cũ "
            f"model_version={self.model_version}, prediction_type={self.prediction_type}"
        )

    def run_backtest(
        self,
        start_date_str="2026-06-01",
        end_date_str="2026-06-11",
        clean_before_run=True,
        limit_hashtags=None,
        include_imputed_actual=False,
        should_stop=None,
    ):
        def stop_requested():
            return should_stop is not None and should_stop()

        self.load_artifacts()

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        warmup_start_date = start_date - timedelta(days=SEQ_LENGTH)

        if clean_before_run:
            self.clean_old_backtest_results()

        history_by_hashtag = self.load_history_rows(
            warmup_start_date=warmup_start_date,
            end_date=end_date,
            limit_hashtags=limit_hashtags,
        )

        target_dates = self.make_date_range(start_date, end_date)

        saved_count = 0
        skipped_count = 0
        missing_sequence_count = 0
        missing_actual_count = 0
        imputed_actual_skipped_count = 0

        absolute_errors = []
        squared_errors = []
        accuracy_scores = []

        logger.info("=" * 80)
        logger.info("🚀 LSTM V3 HISTORICAL BACKTEST")
        logger.info(f"📌 Backtest range: {start_date} → {end_date}")
        logger.info(f"📌 Warmup start: {warmup_start_date}")
        logger.info(f"📌 Model version: {self.model_version}")
        logger.info(f"📌 Prediction type: {self.prediction_type}")
        logger.info(f"📌 Hashtags loaded: {len(history_by_hashtag)}")
        logger.info("=" * 80)

        for hashtag_id, date_map in history_by_hashtag.items():
            if stop_requested():
                logger.warning("🛑 Backtest đã bị dừng bởi admin.")
                break

            for target_date in target_dates:
                actual_row = date_map.get(target_date)

                if not actual_row:
                    missing_actual_count += 1
                    continue

                if (
                    not include_imputed_actual
                    and bool(getattr(actual_row, "is_imputed", False))
                ):
                    imputed_actual_skipped_count += 1
                    continue

                window_dates = [
                    target_date - timedelta(days=SEQ_LENGTH),
                    target_date - timedelta(days=SEQ_LENGTH - 1),
                    target_date - timedelta(days=SEQ_LENGTH - 2),
                    target_date - timedelta(days=SEQ_LENGTH - 3),
                ]

                window_rows = []

                for date_item in window_dates:
                    row = date_map.get(date_item)

                    if not row:
                        window_rows = []
                        break

                    window_rows.append(row)

                if len(window_rows) != SEQ_LENGTH:
                    missing_sequence_count += 1
                    continue

                try:
                    predicted_value = self.predict_one(window_rows)
                    actual_value = float(getattr(actual_row, TARGET, 0) or 0)

                    accuracy_score = self.calculate_accuracy(
                        predicted_value,
                        actual_value,
                    )

                    abs_error = abs(predicted_value - actual_value)
                    squared_error = abs_error ** 2

                    absolute_errors.append(abs_error)
                    squared_errors.append(squared_error)
                    accuracy_scores.append(accuracy_score)

                    prediction_date = target_date - timedelta(days=1)

                    prediction = Prediction(
                        trend_id=None,
                        hashtag_id=hashtag_id,
                        prediction_type=self.prediction_type,
                        prediction_date=prediction_date,
                        predicted_for_date=target_date,
                        predicted_value=float(predicted_value),
                        actual_value=float(actual_value),
                        accuracy_score=float(accuracy_score),
                        model_version=self.model_version,
                        created_at=datetime.now(timezone.utc),
                    )

                    self.db.add(prediction)
                    saved_count += 1

                    if saved_count % 100 == 0:
                        self.db.commit()
                        logger.info(f"✅ Đã lưu {saved_count} backtest predictions...")

                except Exception as error:
                    self.db.rollback()
                    skipped_count += 1
                    logger.warning(
                        f"⚠️ Bỏ qua hashtag_id={hashtag_id}, target_date={target_date}: {error}"
                    )

        self.db.commit()

        mae = float(np.mean(absolute_errors)) if absolute_errors else 0
        rmse = float(sqrt(np.mean(squared_errors))) if squared_errors else 0
        avg_accuracy = float(np.mean(accuracy_scores)) if accuracy_scores else 0

        result = {
            "status": "completed",
            "model_version": self.model_version,
            "prediction_type": self.prediction_type,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "warmup_start_date": str(warmup_start_date),
            "saved_count": saved_count,
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "average_accuracy": round(avg_accuracy, 4),
            "average_accuracy_percent": round(avg_accuracy * 100, 2),
            "missing_sequence_count": missing_sequence_count,
            "missing_actual_count": missing_actual_count,
            "imputed_actual_skipped_count": imputed_actual_skipped_count,
            "skipped_count": skipped_count,
            "include_imputed_actual": include_imputed_actual,
        }

        logger.info("=" * 80)
        logger.info("🏁 BACKTEST COMPLETED")
        logger.info(f"✅ Saved: {saved_count}")
        logger.info(f"📌 MAE: {result['mae']}")
        logger.info(f"📌 RMSE: {result['rmse']}")
        logger.info(f"📌 Avg accuracy: {result['average_accuracy_percent']}%")
        logger.info(f"⚠️ Missing sequence: {missing_sequence_count}")
        logger.info(f"⚠️ Missing actual: {missing_actual_count}")
        logger.info(f"⚠️ Imputed actual skipped: {imputed_actual_skipped_count}")
        logger.info("=" * 80)

        return result


def main():
    parser = argparse.ArgumentParser(description="Run LSTM v3 historical backtest")

    parser.add_argument("--start-date", default="2026-06-01")
    parser.add_argument("--end-date", default="2026-06-11")

    parser.add_argument(
        "--model-version",
        default=DEFAULT_MODEL_VERSION,
    )

    parser.add_argument(
        "--prediction-type",
        default=DEFAULT_PREDICTION_TYPE,
    )

    parser.add_argument(
        "--limit-hashtags",
        type=int,
        default=None,
        help="Test nhanh với số hashtag giới hạn. Bỏ trống để chạy toàn bộ.",
    )

    parser.add_argument(
        "--include-imputed-actual",
        action="store_true",
        help="Cho phép dùng actual bị imputed. Mặc định sẽ bỏ qua actual imputed.",
    )

    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Không xóa kết quả backtest cũ trước khi chạy.",
    )

    args = parser.parse_args()

    backtester = LSTMBacktester(
        model_version=args.model_version,
        prediction_type=args.prediction_type,
    )

    try:
        result = backtester.run_backtest(
            start_date_str=args.start_date,
            end_date_str=args.end_date,
            clean_before_run=not args.no_clean,
            limit_hashtags=args.limit_hashtags,
            include_imputed_actual=args.include_imputed_actual,
        )

        print(result)

    finally:
        backtester.close()


if __name__ == "__main__":
    main()