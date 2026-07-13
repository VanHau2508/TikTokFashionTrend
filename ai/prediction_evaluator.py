import argparse
import logging
from datetime import datetime

from sqlalchemy import and_, func

from database.config import SessionLocal
from database.models import Prediction, TrendHistory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LSTM_V3_MODEL_VERSION = "lstm_trend_history_growth_v3"
PREDICTION_TYPE = "view_growth"


class PredictionEvaluator:
    """
    Đánh giá kết quả dự đoán LSTM v3.

    Chạy hằng ngày sau khi đã:
    1) sync_video_stats
    2) build trend_history cho ngày mới

    Mặc định evaluator có tính idempotent:
    - Chỉ đánh giá prediction actual_value IS NULL.
    - Chạy lặp lại nhiều lần không ghi đè prediction đã đánh giá.

    Nếu cần tính lại điểm vì đã rebuild trend_history, dùng force_recalculate=True
    hoặc CLI --force-recalculate kèm --from-date/--to-date để giới hạn phạm vi.
    """

    def __init__(self):
        self.db = SessionLocal()

    @staticmethod
    def _parse_date(value):
        if value in [None, ""]:
            return None
        if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
            return value
        return datetime.strptime(str(value), "%Y-%m-%d").date()

    def calculate_accuracy(self, predicted_value, actual_value):
        predicted = float(predicted_value or 0)
        actual = float(actual_value or 0)

        if predicted == 0 and actual == 0:
            return 1.0

        error_rate = abs(predicted - actual) / (abs(actual) + 1)
        accuracy = max(0, 1 - error_rate)
        return round(accuracy, 4)

    def evaluate_predictions(
        self,
        limit=None,
        should_stop=None,
        force_recalculate=False,
        from_date=None,
        to_date=None,
    ):
        def stop_requested():
            return should_stop is not None and should_stop()

        from_date = self._parse_date(from_date)
        to_date = self._parse_date(to_date)

        try:
            actual_max_date = self.db.query(func.max(TrendHistory.date)).scalar()

            if not actual_max_date:
                logger.warning("⚠️ Chưa có dữ liệu trend_history để evaluate predictions.")
                return {
                    "status": "completed",
                    "evaluated_count": 0,
                    "missing_actual_count": 0,
                    "skipped_count": 0,
                    "not_due_yet_count": 0,
                    "actual_max_date": None,
                    "message": "Chưa có dữ liệu trend_history để đánh giá prediction.",
                }

            waiting_query = (
                self.db.query(Prediction)
                .filter(Prediction.model_version == LSTM_V3_MODEL_VERSION)
                .filter(Prediction.prediction_type == PREDICTION_TYPE)
                .filter(Prediction.actual_value.is_(None))
            )

            total_waiting = waiting_query.count()

            not_due_yet = (
                waiting_query
                .filter(Prediction.predicted_for_date > actual_max_date)
                .count()
            )

            query = (
                self.db.query(Prediction)
                .filter(Prediction.model_version == LSTM_V3_MODEL_VERSION)
                .filter(Prediction.prediction_type == PREDICTION_TYPE)
                .filter(Prediction.predicted_for_date <= actual_max_date)
            )

            if not force_recalculate:
                query = query.filter(Prediction.actual_value.is_(None))

            if from_date:
                query = query.filter(Prediction.predicted_for_date >= from_date)
            if to_date:
                query = query.filter(Prediction.predicted_for_date <= to_date)

            query = query.order_by(Prediction.predicted_for_date.asc())

            if limit:
                query = query.limit(limit)

            predictions = query.all()

            evaluated_count = 0
            missing_actual_count = 0
            skipped_count = 0

            logger.info("=" * 80)
            logger.info("🚀 EVALUATE LSTM V3 PREDICTIONS")
            logger.info(f"📌 Actual max date in trend_history: {actual_max_date}")
            logger.info(f"📌 Waiting predictions: {total_waiting}")
            logger.info(f"📌 Not due yet: {not_due_yet}")
            logger.info(f"📌 Force recalculate: {force_recalculate}")
            logger.info(f"📌 Date filter: {from_date or 'min'} → {to_date or 'max'}")
            logger.info(f"📌 Predictions cần đánh giá: {len(predictions)}")
            logger.info("=" * 80)

            for prediction in predictions:
                if stop_requested():
                    logger.warning("🛑 Evaluate prediction đã bị dừng bởi admin.")
                    return {
                        "status": "cancelled",
                        "evaluated_count": evaluated_count,
                        "missing_actual_count": missing_actual_count,
                        "skipped_count": skipped_count,
                        "total_waiting_predictions": total_waiting,
                        "not_due_yet_count": not_due_yet,
                        "actual_max_date": str(actual_max_date),
                        "message": "Task đã được dừng bởi admin.",
                    }

                if not prediction.hashtag_id or not prediction.predicted_for_date:
                    skipped_count += 1
                    continue

                actual_history = (
                    self.db.query(TrendHistory)
                    .filter(
                        and_(
                            TrendHistory.hashtag_id == prediction.hashtag_id,
                            TrendHistory.date == prediction.predicted_for_date,
                        )
                    )
                    .first()
                )

                if not actual_history:
                    missing_actual_count += 1
                    continue

                actual_value = float(actual_history.view_growth or 0)
                accuracy_score = self.calculate_accuracy(
                    prediction.predicted_value,
                    actual_value,
                )

                prediction.actual_value = actual_value
                prediction.accuracy_score = accuracy_score

                self.db.commit()
                evaluated_count += 1

                logger.info(
                    f"✅ prediction_id={prediction.prediction_id} | "
                    f"predicted={float(prediction.predicted_value or 0):,.0f} | "
                    f"actual={actual_value:,.0f} | "
                    f"accuracy={accuracy_score * 100:.2f}%"
                )

            logger.info("=" * 80)
            logger.info("🏁 Evaluate prediction completed")
            logger.info(f"✅ Evaluated/Recalculated: {evaluated_count}")
            logger.info(f"⚠️ Missing actual: {missing_actual_count}")
            logger.info(f"⏭️ Skipped: {skipped_count}")
            logger.info(f"📌 Actual max date: {actual_max_date}")
            logger.info("=" * 80)

            return {
                "status": "completed",
                "evaluated_count": evaluated_count,
                "missing_actual_count": missing_actual_count,
                "skipped_count": skipped_count,
                "total_waiting_predictions": total_waiting,
                "not_due_yet_count": not_due_yet,
                "actual_max_date": str(actual_max_date),
                "model_version": LSTM_V3_MODEL_VERSION,
                "prediction_type": PREDICTION_TYPE,
                "force_recalculate": force_recalculate,
                "message": "Evaluate prediction completed.",
            }

        except Exception as error:
            self.db.rollback()
            logger.error(f"❌ Evaluate prediction failed: {error}")
            raise

        finally:
            self.db.close()


def _build_arg_parser():
    parser = argparse.ArgumentParser(description="Evaluate LSTM v3 predictions safely")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số prediction cần đánh giá")
    parser.add_argument("--force-recalculate", action="store_true", help="Tính lại cả prediction đã có actual_value")
    parser.add_argument("--from-date", default=None, help="YYYY-MM-DD, lọc predicted_for_date từ ngày này")
    parser.add_argument("--to-date", default=None, help="YYYY-MM-DD, lọc predicted_for_date đến ngày này")
    return parser


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    evaluator = PredictionEvaluator()
    evaluator.evaluate_predictions(
        limit=args.limit,
        force_recalculate=args.force_recalculate,
        from_date=args.from_date,
        to_date=args.to_date,
    )
