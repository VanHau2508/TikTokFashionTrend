import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Archive,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  Database,
  DatabaseBackup,
  LineChart,
  Loader2,
  RefreshCcw,
  Search,
  ShieldCheck,
  Shirt,
  XCircle,
} from "lucide-react";

import {
  getAdminTaskHistory,
  getDataQualitySummary,
  getModelEvaluation,
  getPipelineStatus,
  runBackupDatabase,
  runBuildTrendHistory,
  runCrawlHashtags,
  runPrediction,
  runProcessYolo,
  runSyncStats,
  cancelAdminTask,
  runEvaluatePredictions,
} from "../../controllers/admin/adminController";

function todayString() {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoString(days) {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

function formatDateTime(value) {
  if (!value) return "—";

  try {
    return new Date(value).toLocaleString("vi-VN");
  } catch {
    return value;
  }
}

function getStatusIcon(status) {
  if (status === "completed") return <CheckCircle2 size={16} />;
  if (status === "failed") return <XCircle size={16} />;
  if (status === "running") return <Loader2 size={16} className="spin-icon" />;
  return <Clock3 size={16} />;
}

function parseHashtags(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim().replace("#", ""))
    .filter(Boolean);
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "0";

  const numberValue = Number(value);

  if (Number.isNaN(numberValue)) return "0";

  return numberValue.toLocaleString("vi-VN");
}

function formatPercent(value) {
  if (value === null || value === undefined || value === "") return "0%";

  const numberValue = Number(value);

  if (Number.isNaN(numberValue)) return "0%";

  return `${numberValue.toFixed(2)}%`;
}

function formatRatioPercent(value) {
  if (value === null || value === undefined || value === "") return "0%";

  const numberValue = Number(value);

  if (Number.isNaN(numberValue)) return "0%";

  const percentValue = numberValue <= 1 ? numberValue * 100 : numberValue;

  return `${percentValue.toFixed(2)}%`;
}

const HISTORICAL_BACKTEST_METRICS = {
  period: "01/06/2026 – 11/06/2026",
  regressionAccuracy: 0.3854,
  hitRateAt10: 0.5818,
  highGrowthPrecision: 0.8377,
  totalSamples: 14751,
  totalHashtags: 1341,
};

const LATEST_TREND_DETECTION_METRICS = {
  period: "27/06/2026 → 28/06/2026",
  hitTop10: 8,
  predictedTop10: 10,
  hitRateAt10: 0.8,
};

function getStatusMeta(status) {
  const normalized = String(status || "not_run").toLowerCase();

  if (normalized === "completed" || normalized === "success") {
    return {
      label: "Hoàn tất",
      className: "status-completed",
      icon: CheckCircle2,
    };
  }

  if (normalized === "cancel_requested") {
    return {
      label: "Đang dừng",
      className: "status-running",
      icon: AlertTriangle,
    };
  }

  if (normalized === "cancelled" || normalized === "canceled") {
    return {
      label: "Đã dừng",
      className: "status-not-run",
      icon: XCircle,
    };
  }

  if (
    normalized === "running" ||
    normalized === "queued" ||
    normalized === "pending"
  ) {
    return {
      label: normalized === "queued" ? "Đang chờ" : "Đang chạy",
      className: "status-running",
      icon: Clock3,
    };
  }

  if (normalized === "failed" || normalized === "error") {
    return {
      label: "Thất bại",
      className: "status-failed",
      icon: XCircle,
    };
  }

  return {
    label: "Chưa chạy",
    className: "status-not-run",
    icon: AlertTriangle,
  };
}

function AdminMetricCard({ title, value, description, icon: Icon }) {
  return (
    <div className="admin-metric-card">
      <div className="admin-metric-icon">
        <Icon size={20} />
      </div>

      <div>
        <p>{title}</p>
        <strong>{value}</strong>
        {description && <span>{description}</span>}
      </div>
    </div>
  );
}

function AdminTaskPanel({
  step,
  title,
  description,
  icon: Icon,
  children,
  buttonText,
  loading,
  onRun,
}) {
  return (
    <div className="admin-task-panel">
      <div className="admin-task-panel-top">
        <div className="admin-task-step">{step}</div>

        <div className="admin-task-icon">
          <Icon size={24} />
        </div>
      </div>

      <h4>{title}</h4>
      <p>{description}</p>

      <div className="admin-task-form">{children}</div>

      <button
        className="btn-primary-pink admin-task-run-btn"
        onClick={onRun}
        disabled={loading}
      >
        {loading ? (
          <>
            <Loader2 size={17} className="spin-icon" />
            Đang chạy...
          </>
        ) : (
          buttonText
        )}
      </button>
    </div>
  );
}

function getFriendlyTaskError(errorText = "") {
  const text = String(errorText || "");

  if (!text.trim()) {
    return "";
  }

  if (
    text.includes("Target page, context or browser has been closed") ||
    text.includes("TargetClosedError")
  ) {
    return "Tác vụ đã bị dừng do trình duyệt xử lý dữ liệu bị đóng.";
  }

  if (
    text.includes("KeyboardInterrupt") ||
    text.includes("CancelledError") ||
    text.includes("Future exception was never retrieved")
  ) {
    return "Tác vụ đã bị hủy hoặc bị dừng đột ngột trong quá trình xử lý.";
  }

  if (text.includes("pg_dump") || text.includes("PATH")) {
    return "Không thể backup database do chưa tìm thấy công cụ PostgreSQL trong PATH.";
  }

  if (text.includes("Timeout")) {
    return "Tác vụ xử lý quá thời gian cho phép. Vui lòng thử lại với limit nhỏ hơn.";
  }

  if (text.includes("403") || text.includes("Access denied")) {
    return "Không thể truy cập nguồn dữ liệu. Vui lòng kiểm tra quyền truy cập hoặc cấu hình hệ thống.";
  }

  return text.split("\n")[0].slice(0, 180);
}

function hasLongTechnicalError(errorText = "") {
  const text = String(errorText || "");
  return (
    text.length > 200 ||
    text.includes("Traceback") ||
    text.includes("File ") ||
    text.includes("ERROR:")
  );
}

function getSafeLogs(logs = []) {
  return (logs || []).map((log) => ({
    ...log,
    message: getFriendlyTaskError(log.message || ""),
    raw: log.message || "",
  }));
}

function AdminTasks() {
  const [taskLoading, setTaskLoading] = useState("");
  const [message, setMessage] = useState("");
  const [taskHistory, setTaskHistory] = useState([]);

  const [summary, setSummary] = useState(null);
  const [pipeline, setPipeline] = useState([]);
  const [modelEvaluation, setModelEvaluation] = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewError, setOverviewError] = useState("");
  const [stoppingTaskId, setStoppingTaskId] = useState(null);
  const [evaluateForm, setEvaluateForm] = useState({
    limit: 1000,
  });

  const [crawlForm, setCrawlForm] = useState({
    hashtags: "y2k, vintage, streetwear",
    max_videos: 300,
    max_scrolls: 30,
  });

  const [yoloForm, setYoloForm] = useState({
    batch_size: 20,
    confidence: 0.4,
  });

  const [syncForm, setSyncForm] = useState({
    hours_gap: 16,
    limit: 2500,
  });

  const [historyForm, setHistoryForm] = useState({
    start_date: todayString(),
    end_date: todayString(),
    min_distinct_stat_days: 2,
    clean_before_build: true,
  });

  const [predictionForm, setPredictionForm] = useState({
    limit: 100,
  });

  const [backupForm, setBackupForm] = useState({
    file_prefix: "backup",
    timeout_seconds: 300,
  });

  const latestRunningTask = useMemo(() => {
    return taskHistory.find((task) => task.status === "running");
  }, [taskHistory]);

  const lstmEvaluation = modelEvaluation?.lstm || {};

  useEffect(() => {
    loadTaskHistory();
    loadAdminOverview();

    const historyTimer = setInterval(() => {
      loadTaskHistory();
    }, 5000);

    const overviewTimer = setInterval(() => {
      loadAdminOverview();
    }, 15000);

    return () => {
      clearInterval(historyTimer);
      clearInterval(overviewTimer);
    };
  }, []);

  const loadAdminOverview = async () => {
    try {
      setOverviewLoading(true);
      setOverviewError("");

      const [summaryResult, pipelineResult, modelResult] =
        await Promise.allSettled([
          getDataQualitySummary(),
          getPipelineStatus(),
          getModelEvaluation(),
        ]);

      const summaryData =
        summaryResult.status === "fulfilled" ? summaryResult.value || {} : {};

      const pipelineData =
        pipelineResult.status === "fulfilled" ? pipelineResult.value || {} : {};

      const modelData =
        modelResult.status === "fulfilled" ? modelResult.value || {} : {};

      setSummary(summaryData);
      setPipeline(pipelineData.pipeline || []);
      setModelEvaluation(modelData);
    } catch (error) {
      console.error("Admin overview error:", error);
      setOverviewError("Không thể tải dữ liệu tổng quan hệ thống.");
    } finally {
      setOverviewLoading(false);
    }
  };

  const loadTaskHistory = async () => {
    try {
      const result = await getAdminTaskHistory();
      setTaskHistory(result.items || []);
    } catch (error) {
      console.error("Admin task history error:", error);
    }
  };

  const handleRunTask = async (taskName, callback, payload) => {
    try {
      setTaskLoading(taskName);
      setMessage("");

      const result = await callback(payload);

      setMessage(result.message || "Tác vụ đã được đưa vào hàng chờ.");
      await loadTaskHistory();
      await loadAdminOverview();
    } catch (error) {
      setMessage(
        error.response?.data?.detail ||
          "Không thể chạy tác vụ. Kiểm tra backend hoặc quyền admin."
      );
    } finally {
      setTaskLoading("");
    }
  };

  const handleCancelTask = async (taskId) => {
    if (!taskId) return;

    const confirmed = window.confirm(
      "Bạn có chắc muốn dừng tác vụ này không?"
    );

    if (!confirmed) return;

    try {
      setStoppingTaskId(taskId);

      const result = await cancelAdminTask(taskId);

      setMessage(result.message || "Đã gửi yêu cầu dừng task.");

      await loadTaskHistory();
      await loadAdminOverview();
    } catch (error) {
      setMessage(
        error.response?.data?.detail ||
          "Không thể dừng task. Vui lòng kiểm tra backend."
      );
    } finally {
      setStoppingTaskId(null);
    }
  };

  const handleCrawl = () => {
    const hashtags = parseHashtags(crawlForm.hashtags);

    if (hashtags.length === 0) {
      setMessage("Vui lòng nhập ít nhất một hashtag.");
      return;
    }

    handleRunTask("crawl", runCrawlHashtags, {
      hashtags,
      max_videos: Number(crawlForm.max_videos),
      max_scrolls: Number(crawlForm.max_scrolls),
    });
  };

  return (
    <div className="admin-page admin-tasks-page">
      <h1 className="page-title">Tác vụ hệ thống</h1>
      <p className="page-subtitle">
        Trung tâm điều khiển pipeline AI: crawl dữ liệu, nhận diện vật phẩm,
        đồng bộ chỉ số, tạo lịch sử xu hướng, đánh giá dự đoán, dự đoán LSTM
        và backup dữ liệu.
      </p>

      {message && <div className="admin-message">{message}</div>}

      {latestRunningTask && (
        <div className="admin-running-banner">
          <div className="admin-running-left">
            <Loader2 size={18} className="spin-icon" />
            Đang chạy: <strong>{latestRunningTask.title}</strong>
          </div>

          <button
            type="button"
            className="admin-stop-btn"
            onClick={() => handleCancelTask(latestRunningTask.task_id)}
            disabled={stoppingTaskId === latestRunningTask.task_id}
          >
            <XCircle size={16} />
            {stoppingTaskId === latestRunningTask.task_id ? "Đang dừng..." : "Dừng task"}
          </button>
        </div>
      )}

      <div className="admin-overview-toolbar">
        <div>
          <h5>Tổng quan vận hành hệ thống</h5>
          <p>
            Theo dõi chất lượng dữ liệu, trạng thái pipeline và hiệu quả xử lý AI.
          </p>
        </div>

        <button
          type="button"
          className="admin-refresh-btn"
          onClick={() => {
            loadTaskHistory();
            loadAdminOverview();
          }}
          disabled={overviewLoading}
        >
          <RefreshCcw size={16} />
          {overviewLoading ? "Đang tải..." : "Làm mới"}
        </button>
      </div>

      {overviewError && (
        <div className="admin-error-message">{overviewError}</div>
      )}

      {summary && (
        <div className="admin-overview-section mb-4">
          <div className="section-header">
            <div>
              <h5>Tóm tắt dữ liệu</h5>
              <span>Các chỉ số quan trọng cho pipeline AI hiện tại</span>
            </div>
          </div>

          <div className="admin-metric-grid compact">
            <AdminMetricCard
              title="Video hợp lệ 2026"
              value={formatNumber(summary.videos)}
              description={`${formatNumber(summary.analyzed_videos)} đã phân tích · ${formatNumber(summary.pending_videos)} đang chờ`}
              icon={Database}
            />

            <AdminMetricCard
              title="YOLO success"
              value={formatPercent(summary.processed_success_rate || summary.yolo_success_rate)}
              description={`${formatNumber(summary.yolo_success)} video nhận diện thành công`}
              icon={ShieldCheck}
            />

            <AdminMetricCard
              title="Trend History"
              value={formatNumber(summary.trend_history)}
              description="Dữ liệu lịch sử dùng cho LSTM"
              icon={LineChart}
            />

            <AdminMetricCard
              title="Predictions"
              value={formatNumber(summary.predictions)}
              description="Kết quả dự đoán đang lưu"
              icon={BrainCircuit}
            />
          </div>
          </div>
      )}

      <div className="admin-overview-two-columns">
        <div className="admin-overview-section">
          <div className="section-header">
            <div>
              <h5>Trạng thái pipeline</h5>
            </div>
          </div>

          <div className="pipeline-list">
            {pipeline.length > 0 ? (
              pipeline.map((item) => {
                const statusMeta = getStatusMeta(item.status);
                const StatusIcon = statusMeta.icon;

                return (
                  <div className="pipeline-item" key={item.task_type}>
                    <div className="pipeline-left">
                      <div
                        className={`pipeline-status-icon ${statusMeta.className}`}
                      >
                        <StatusIcon size={16} />
                      </div>

                      <div>
                        <strong>{item.title}</strong>
                        <p>{item.description || item.task_type}</p>

                        {item.error_message && (
                          <div className="pipeline-error-box">
                            <span className="pipeline-error">
                              {getFriendlyTaskError(item.error_message)}
                            </span>

                            {hasLongTechnicalError(item.error_message) && (
                              <details className="technical-error-details">
                                <summary>Chi tiết kỹ thuật</summary>
                                <pre>{item.error_message}</pre>
                              </details>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="pipeline-right">
                      <span className={`pipeline-badge ${statusMeta.className}`}>
                        {statusMeta.label}
                      </span>
                      <small>
                        {item.completed_at
                          ? formatDateTime(item.completed_at)
                          : formatDateTime(item.started_at)}
                      </small>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="admin-empty-box">
                Chưa có dữ liệu pipeline.
              </div>
            )}
          </div>
        </div>

        <div className="admin-overview-section">
          <div className="section-header">
            <div>
              <h5>Đánh giá mô hình</h5>
            </div>
          </div>

          <div className="model-evaluation-box">
            <div className="model-card">
              <div className="model-card-title">
                <ShieldCheck size={18} />
                <strong>YOLOv8m Fashion Detection</strong>
              </div>

              <div className="model-section-label">Pipeline hiện tại</div>

              <div className="model-stat-row">
                <span>Video trong phạm vi</span>
                <strong>{formatNumber(modelEvaluation?.yolo?.total_in_scope)}</strong>
              </div>

              <div className="model-stat-row">
                <span>Nhận diện thành công</span>
                <strong>{formatNumber(modelEvaluation?.yolo?.success_count)}</strong>
              </div>

              <div className="model-stat-row">
                <span>Tỉ lệ nhận diện thời trang</span>
                <strong>{formatPercent(modelEvaluation?.yolo?.fashion_detection_rate)}</strong>
              </div>

              <div className="model-stat-row">
                <span>Tỉ lệ thành công đã xử lý</span>
                <strong>{formatPercent(modelEvaluation?.yolo?.processed_success_rate)}</strong>
              </div>

              <div className="model-stat-row">
                <span>Độ tin cậy</span>
                <strong>
                  {Number(
                    modelEvaluation?.yolo?.average_yolo_item_confidence || 0
                  ).toFixed(4)}
                </strong>
              </div>
            </div>

            <div className="model-card model-card-lstm">
              <div className="model-card-title">
                <BrainCircuit size={18} />
                <strong>LSTM Trend Prediction</strong>
              </div>

              <div className="model-section-label">ĐÁNH GIÁ HIỆN TẠI</div>

              <div className="model-stat-row">
                <span>Tổng dự đoán</span>
                <strong>{formatNumber(lstmEvaluation.total_predictions)}</strong>
              </div>

              <div className="model-stat-row">
                <span>Đã đánh giá</span>
                <strong>{formatNumber(lstmEvaluation.evaluated_predictions)}</strong>
              </div>

              <div className="model-stat-row">
                <span>Chờ dữ liệu thực tế</span>
                <strong>{formatNumber(lstmEvaluation.pending_evaluation)}</strong>
              </div>

              <div className="model-stat-row">
                <span>Độ khớp giá trị</span>
                <strong>{formatRatioPercent(lstmEvaluation.average_accuracy)}</strong>
              </div>

              <div className="model-divider" />

              <div className="model-section-label">ĐÁNH GIÁ GẦN NHẤT</div>

              <div className="model-stat-row">
                <span>Lần đánh giá: </span>
                <strong>{LATEST_TREND_DETECTION_METRICS.period}</strong>
              </div>

              <div className="model-stat-row">
                <span>Dự đoán đúng Top 10</span>
                <strong>
                  {LATEST_TREND_DETECTION_METRICS.hitTop10}/
                  {LATEST_TREND_DETECTION_METRICS.predictedTop10}
                </strong>
              </div>

              <div className="model-stat-row important">
                <span>Tỷ lệ đúng Top 10</span>
                <strong>
                  {formatRatioPercent(
                    LATEST_TREND_DETECTION_METRICS.hitRateAt10
                  )}
                </strong>
              </div>

              <div className="model-divider" />

              <div className="model-section-label">Đánh giá tổng quan</div>

              <div className="model-stat-row">
                <span>Thời gian đánh giá</span>
                <strong>{HISTORICAL_BACKTEST_METRICS.period}</strong>
              </div>

              <div className="model-stat-row">
                <span>Mẫu đánh giá</span>
                <strong>
                  {formatNumber(HISTORICAL_BACKTEST_METRICS.totalSamples)}
                </strong>
              </div>

              <div className="model-stat-row">
                <span>Số hashtag</span>
                <strong>
                  {formatNumber(HISTORICAL_BACKTEST_METRICS.totalHashtags)}
                </strong>
              </div>

              <div className="model-stat-row">
                <span>Độ khớp giá trị lịch sử</span>
                <strong>
                  {formatRatioPercent(
                    HISTORICAL_BACKTEST_METRICS.regressionAccuracy
                  )}
                </strong>
              </div>

              <div className="model-stat-row benchmark">
                <span>Tỷ lệ đúng Top 10 lịch sử</span>
                <strong>
                  {formatRatioPercent(HISTORICAL_BACKTEST_METRICS.hitRateAt10)}
                </strong>
              </div>

              <div className="model-stat-row benchmark">
                <span>Độ chính xác nhóm tăng trưởng cao</span>
                <strong>
                  {formatRatioPercent(
                    HISTORICAL_BACKTEST_METRICS.highGrowthPrecision
                  )}
                </strong>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="admin-workflow-card mb-4">
        <div className="section-header">
          <div>
            <h5>Quy trình vận hành hệ thống</h5>
            <span>Thứ tự chạy khuyến nghị khi cập nhật dữ liệu hằng ngày</span>
          </div>
        </div>

        <div className="admin-workflow-steps">
          <div>
            <b>1</b>
            <span>Thu thập video</span>
          </div>
          <div>
            <b>2</b>
            <span>Nhận diện YOLOv8m</span>
          </div>
          <div>
            <b>3</b>
            <span>Đồng bộ chỉ số</span>
          </div>
          <div>
            <b>4</b>
            <span>Tạo lịch sử xu hướng</span>
          </div>
          <div>
            <b>5</b>
            <span>Đánh giá dự đoán </span>
          </div>
          <div>
            <b>6</b>
            <span>Dự đoán ngày tiếp theo</span>
          </div>
          <div>
            <b>7</b>
            <span>Sao lưu dữ liệu</span>
          </div>
        </div>
      </div>

      <div className="admin-task-grid">
        <AdminTaskPanel
          step="01"
          title="Thu thập video TikTok theo hashtag"
          description="Nhập hashtag cần lấy dữ liệu, số lượng video và số lần cuộn trang."
          icon={Search}
          buttonText="Chạy crawler"
          loading={taskLoading === "crawl"}
          onRun={handleCrawl}
        >
          <label>Hashtags</label>
          <input
            type="text"
            value={crawlForm.hashtags}
            onChange={(event) =>
              setCrawlForm({ ...crawlForm, hashtags: event.target.value })
            }
            placeholder="Nhập hashtag, cách nhau bằng dấu phẩy. Ví dụ: y2k, vintage"
          />

          <div className="admin-task-two-cols">
            <div>
              <label>Số lượng video tối đa</label>
              <input
                type="number"
                value={crawlForm.max_videos}
                onChange={(event) =>
                  setCrawlForm({
                    ...crawlForm,
                    max_videos: event.target.value,
                  })
                }
              />
            </div>

            <div>
              <label>Số lần cuộn trang</label>
              <input
                type="number"
                value={crawlForm.max_scrolls}
                onChange={(event) =>
                  setCrawlForm({
                    ...crawlForm,
                    max_scrolls: event.target.value,
                  })
                }
              />
            </div>
          </div>
        </AdminTaskPanel>

        <AdminTaskPanel
          step="02"
          title="Nhận diện thời trang bằng YOLOv8m"
          description="Xử lý video pending/success theo pipeline, lọc video thời trang và lưu item nhận diện nếu có."
          icon={Shirt}
          buttonText="Chạy YOLOv8m"
          loading={taskLoading === "yolo"}
          onRun={() =>
            handleRunTask("yolo", runProcessYolo, {
              batch_size: Number(yoloForm.batch_size),
              confidence: Number(yoloForm.confidence),
            })
          }
        >
          <div className="admin-task-two-cols">
            <div>
              <label>Batch size</label>
              <input
                type="number"
                value={yoloForm.batch_size}
                onChange={(event) =>
                  setYoloForm({ ...yoloForm, batch_size: event.target.value })
                }
              />
            </div>

            <div>
              <label>Confidence</label>
              <input
                type="number"
                step="0.05"
                value={yoloForm.confidence}
                onChange={(event) =>
                  setYoloForm({ ...yoloForm, confidence: event.target.value })
                }
              />
            </div>
          </div>
        </AdminTaskPanel>

        <AdminTaskPanel
          step="03"
          title="Đồng bộ chỉ số video"
          description="Cập nhật lượt xem, lượt thích, bình luận và chia sẻ cho các video đã AI xác nhận."
          icon={RefreshCcw}
          buttonText="Khởi chạy đồng bộ"
          loading={taskLoading === "sync"}
          onRun={() => {
            const hoursGap = Number(syncForm.hours_gap || 16);
            const limit = Number(syncForm.limit || 2500);

            if (!Number.isFinite(hoursGap) || hoursGap <= 0) {
              setMessage("Hours gap phải lớn hơn 0.");
              return;
            }

            if (!Number.isFinite(limit) || limit <= 0) {
              setMessage("Limit phải lớn hơn 0.");
              return;
            }

            handleRunTask("sync", runSyncStats, {
              hours_gap: hoursGap,
              limit,
            });
          }}
        >
          <div className="admin-task-two-cols">
            <div>
              <label>Hours gap</label>
              <input
                type="number"
                value={syncForm.hours_gap ?? ""}
                onChange={(event) =>
                  setSyncForm({ ...syncForm, hours_gap: event.target.value })
                }
              />
            </div>

            <div>
              <label>Limit</label>
              <input
              type="number"
              value={syncForm.limit ?? ""}
              onChange={(event) =>
                setSyncForm({ ...syncForm, limit: event.target.value })
              }
            />
            </div>
          </div>
        </AdminTaskPanel>

        <AdminTaskPanel
          step="04"
          title="Xây dựng lịch sử xu hướng"
          description="Build lại trend_history từ video_stats. Với vận hành hằng ngày, nên build hôm nay sau khi sync stats xong; Clean giúp rebuild sạch dữ liệu tổng hợp của ngày đang chọn."
          icon={LineChart}
          buttonText="Tạo lịch sử xu hướng"
          loading={taskLoading === "history"}
          onRun={() =>
            handleRunTask("history", runBuildTrendHistory, {
              start_date: historyForm.start_date,
              end_date: historyForm.end_date,
              min_distinct_stat_days: Number(
                historyForm.min_distinct_stat_days
              ),
              clean_before_build: historyForm.clean_before_build,
            })
          }
        >
          <div className="admin-task-two-cols">
            <div>
              <label>Ngày bắt đầu</label>
              <input
                type="date"
                value={historyForm.start_date}
                onChange={(event) =>
                  setHistoryForm({
                    ...historyForm,
                    start_date: event.target.value,
                  })
                }
              />
            </div>

            <div>
              <label>Ngày kết thúc</label>
              <input
                type="date"
                value={historyForm.end_date}
                onChange={(event) =>
                  setHistoryForm({
                    ...historyForm,
                    end_date: event.target.value,
                  })
                }
              />
            </div>
          </div>

          <div className="admin-task-two-cols">
            <div>
              <label>Ngày tối thiểu</label>
              <input
                type="number"
                value={historyForm.min_distinct_stat_days}
                onChange={(event) =>
                  setHistoryForm({
                    ...historyForm,
                    min_distinct_stat_days: event.target.value,
                  })
                }
              />
            </div>

            <div className="admin-checkbox-row">
              <input
                type="checkbox"
                checked={historyForm.clean_before_build}
                onChange={(event) =>
                  setHistoryForm({
                    ...historyForm,
                    clean_before_build: event.target.checked,
                  })
                }
              />
              <span>Clean trước khi build</span>
            </div>
          </div>
        </AdminTaskPanel>

        <AdminTaskPanel
          step="05"
          title="Đánh giá kết quả dự đoán"
          description="Sau khi đã build trend_history hôm nay, hệ thống so sánh predicted_value với actual_value để đánh giá các prediction cũ đã tới hạn."
          icon={BarChart3}
          buttonText="Đánh giá dự đoán"
          loading={taskLoading === "evaluate"}
          onRun={() =>
            handleRunTask("evaluate", runEvaluatePredictions, {
              limit: Number(evaluateForm.limit),
            })
          }
        >
          <label>Evaluate limit</label>
          <input
            type="number"
            min="1"
            value={evaluateForm.limit}
            onChange={(event) =>
              setEvaluateForm({
                ...evaluateForm,
                limit: event.target.value,
              })
            }
          />
        </AdminTaskPanel>

        <AdminTaskPanel
          step="06"
          title="Dự đoán xu hướng bằng LSTM"
          description="Sau khi đánh giá xong prediction cũ, hệ thống dùng trend_history mới nhất để dự đoán view_growth cho ngày tiếp theo."
          icon={BrainCircuit}
          buttonText="Khởi chạy dự đoán"
          loading={taskLoading === "prediction"}
          onRun={() =>
            handleRunTask("prediction", runPrediction, {
              limit: Number(predictionForm.limit),
            })
          }
        >
          <label>Prediction limit</label>
          <input
            type="number"
            value={predictionForm.limit}
            onChange={(event) =>
              setPredictionForm({
                ...predictionForm,
                limit: event.target.value,
              })
            }
          />
        </AdminTaskPanel>

        <AdminTaskPanel
          step="07"
          title="Sao lưu cơ sở dữ liệu"
          description="Tạo file backup PostgreSQL vào thư mục backups của project."
          icon={DatabaseBackup || Archive}
          buttonText="Tạo bản sao lưu"
          loading={taskLoading === "backup"}
          onRun={() =>
            handleRunTask("backup", runBackupDatabase, {
              file_prefix: backupForm.file_prefix,
              timeout_seconds: Number(backupForm.timeout_seconds),
            })
          }
        >
          <div className="admin-task-two-cols">
            <div>
              <label>File prefix</label>
              <input
                type="text"
                value={backupForm.file_prefix}
                onChange={(event) =>
                  setBackupForm({
                    ...backupForm,
                    file_prefix: event.target.value,
                  })
                }
              />
            </div>

            <div>
              <label>Timeout</label>
              <input
                type="number"
                value={backupForm.timeout_seconds}
                onChange={(event) =>
                  setBackupForm({
                    ...backupForm,
                    timeout_seconds: event.target.value,
                  })
                }
              />
            </div>
          </div>
        </AdminTaskPanel>
      </div>

      <div className="card-box mt-4">
        <div className="section-header">
          <div>
            <h5>Lịch sử công việc</h5>
            <span>Lịch sử các công việc được lưu trong cơ sở dữ liệu</span>
          </div>

          <button className="mini-action-btn" onClick={loadTaskHistory}>
            Làm mới
          </button>
        </div>

        {taskHistory.length === 0 ? (
          <div className="admin-empty-log">
            Chưa có task nào được chạy.
          </div>
        ) : (
          <div className="admin-task-history-list">
            {taskHistory.map((task) => (
              <div
                className={`admin-task-history-item ${task.status}`}
                key={task.task_id}
              >
                <div className="admin-task-history-main">
                  <span className="admin-task-status">
                    {getStatusIcon(task.status)}
                    {task.status}
                  </span>

                  <strong>{task.title}</strong>
                  <p>{task.task_type}</p>
                </div>

                <div className="admin-task-history-meta">
                  <span>Thời gian bắt đầu: {formatDateTime(task.started_at)}</span>
                  <span>Thời gian hoàn thành: {formatDateTime(task.completed_at)}</span>
                </div>

                <div className="admin-task-history-logs">
                  {getSafeLogs(task.logs || [])
                    .slice(-3)
                    .map((log, index) => (
                      <div key={`${task.task_id}-${index}`} className="task-log-line">
                        <p>
                          <b>{formatDateTime(log.time)}:</b> {log.message}
                        </p>

                        {hasLongTechnicalError(log.raw) && (
                          <details className="technical-error-details">
                            <summary>Chi tiết</summary>
                            <pre>{log.raw}</pre>
                          </details>
                        )}
                      </div>
                    ))}

                  {(task.error || task.error_message) && (
                    <div className="task-error-box">
                      <p className="task-error">
                        {getFriendlyTaskError(task.error || task.error_message)}
                      </p>

                      {hasLongTechnicalError(task.error || task.error_message) && (
                        <details className="technical-error-details">
                          <summary>Xem log kỹ thuật</summary>
                          <pre>{task.error || task.error_message}</pre>
                        </details>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default AdminTasks;