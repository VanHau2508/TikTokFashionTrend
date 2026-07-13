import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";

import TrendChart from "../components/TrendChart";
import EmptyState from "../components/EmptyState";

import {
  getTopTrends,
  getEmergingTrends,
  getPredictedTrends,
  getTrendHistory,
} from "../controllers/trendController";

function formatNumber(value, options = {}) {
  const {
    decimals = 0,
    compact = false,
    sign = false,
  } = options;

  const numberValue = Number(value || 0);

  if (!Number.isFinite(numberValue)) return "0";

  const displayValue =
    decimals === 0 ? Math.round(numberValue) : numberValue;

  const formatted = displayValue.toLocaleString("vi-VN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    notation: compact ? "compact" : "standard",
  });

  return sign && displayValue > 0 ? `+${formatted}` : formatted;
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(2)}%`;
}

function getTrendValue(item) {
  return item.view_count || item.view_growth || item.predicted_growth || 0;
}

function getTrendScore(item) {
  return item.trend_score || item.predicted_growth || 0;
}

function getVideoCount(item) {
  return item.video_count ?? item.total_videos ?? item.total ?? item.latest_video_count ?? null;
}

function getMetricLabel(activeTab) {
  if (activeTab === "top") return "Tổng lượt xem";
  if (activeTab === "emerging") return "Lượt xem tăng thêm";
  return "Lượt xem tăng thêm dự đoán";
}

function Trends() {
  const navigate = useNavigate();

  const [topTrends, setTopTrends] = useState([]);
  const [emergingTrends, setEmergingTrends] = useState([]);
  const [predictedTrends, setPredictedTrends] = useState([]);
  const [selectedTrend, setSelectedTrend] = useState(null);
  const [history, setHistory] = useState(null);
  const [activeTab, setActiveTab] = useState("top");
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);

  useEffect(() => {
    loadTrends();
  }, []);

  const loadTrends = async () => {
    try {
      setLoading(true);

      const [topResult, emergingResult, predictedResult] =
        await Promise.allSettled([
          getTopTrends(30),
          getEmergingTrends(30, 5),
          getPredictedTrends(30),
        ]);

      const topData =
        topResult.status === "fulfilled" ? topResult.value || [] : [];

      const emergingData =
        emergingResult.status === "fulfilled" ? emergingResult.value || [] : [];

      const predictedData =
        predictedResult.status === "fulfilled" ? predictedResult.value || [] : [];

      setTopTrends(topData);
      setEmergingTrends(emergingData);
      setPredictedTrends(predictedData);

      if (topData.length > 0) {
        await handleSelectTrend(topData[0]);
      } else if (predictedData.length > 0) {
        await handleSelectTrend(predictedData[0]);
        setActiveTab("predicted");
      }
    } catch (error) {
      console.error("Trend page error:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTrend = async (trend) => {
    if (!trend?.hashtag_id) return;

    try {
      setChartLoading(true);
      setSelectedTrend(trend);

      const response = await getTrendHistory(trend.hashtag_id);
      const result = response.data || response;

      setHistory(result);
    } catch (error) {
      console.error("Trend history error:", error);
      setHistory(null);
    } finally {
      setChartLoading(false);
    }
  };

  if (loading) {
    return <div className="loading-box">Đang tải dữ liệu xu hướng...</div>;
  }

  const historyRows = Array.isArray(history)
    ? history
    : history?.history || history?.items || [];

  const historyLabels = historyRows.map((row) => row.date || row.collected_at);
  const viewGrowthValues = historyRows.map((row) => row.view_growth || 0);
  const engagementValues = historyRows.map((row) => row.engagement_rate || 0);

  const latestHistory = historyRows[historyRows.length - 1] || {};
  const previousHistory = historyRows[historyRows.length - 2] || {};

  const latestGrowth = Number(latestHistory.view_growth || 0);
  const previousGrowth = Number(previousHistory.view_growth || 0);
  const growthDelta = latestGrowth - previousGrowth;

  const currentList =
    activeTab === "top"
      ? topTrends
      : activeTab === "emerging"
      ? emergingTrends
      : predictedTrends;

  return (
    <div>
      <h1 className="page-title">Phân tích xu hướng</h1>
      <p className="page-subtitle">
        So sánh hashtag thịnh hành, xu hướng tăng trưởng nhanh và kết quả dự đoán từ LSTM.
        Chọn một hashtag để xem biểu đồ tăng trưởng theo thời gian.
      </p>

      <div className="trend-summary-grid mb-4">
        <div className="trend-summary-card">
          <span>Hashtag thịnh hành</span>
          <strong>{topTrends.length}</strong>
          <p>Xếp hạng theo tổng lượt xem và điểm xu hướng.</p>
        </div>

        <div className="trend-summary-card">
          <span>Xu hướng tăng trưởng nhanh</span>
          <strong>{emergingTrends.length}</strong>
          <p>Hashtag có lượt xem tăng thêm nổi bật gần nhất.</p>
        </div>

        <div className="trend-summary-card">
          <span>Dự đoán LSTM</span>
          <strong>{predictedTrends.length}</strong>
          <p>Hashtag được dự đoán sẽ tăng trưởng.</p>
        </div>
      </div>

      <div className="row g-3 mb-4">
        <div className="col-lg-8">
          {selectedTrend ? (
            <div className="trend-selected-panel">
              <div className="section-header">
                <div>
                  <h5>Tốc độ tăng trưởng #{selectedTrend.tag_name}</h5>
                  <span>
                    Theo dõi lượt xem tăng thêm và tỷ lệ tương tác của hashtag theo thời gian.
                  </span>
                </div>

                <button
                  className="hashtag-detail-btn"
                  onClick={() => navigate(`/app/hashtags/${selectedTrend.hashtag_id}`)}
                >
                  Xem chi tiết hashtag
                </button>
              </div>

              {historyRows.length > 0 && (
                <div className="timeline-insight-card mb-4">
                  <div className="timeline-card-header">
                    <h4>#{selectedTrend.tag_name}</h4>
                    <span>{formatNumber(historyRows.length)} mốc dữ liệu</span>
                  </div>

                  <div className="timeline-main-value">
                    {formatNumber(latestGrowth)}
                    <small>lượt xem tăng thêm gần nhất</small>
                  </div>

                  <div
                    className={
                      growthDelta >= 0
                        ? "trend-delta positive"
                        : "trend-delta negative"
                    }
                  >
                    <ArrowUpRight size={16} />
                    {growthDelta >= 0 ? "+" : ""}
                    {formatNumber(growthDelta)} so với mốc trước
                  </div>

                  <div className="mini-bar-list">
                    {historyRows.slice(-6).map((row) => {
                      const maxGrowth = Math.max(
                        ...historyRows.map((h) => Number(h.view_growth || 0)),
                        1
                      );

                      const width = Math.min(
                        100,
                        (Number(row.view_growth || 0) / maxGrowth) * 100
                      );

                      return (
                        <div className="mini-bar-row" key={row.date || row.collected_at}>
                          <span>{row.date || row.collected_at}</span>
                          <div>
                            <i style={{ width: `${width}%` }} />
                          </div>
                          <b>{formatNumber(row.view_growth)}</b>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {chartLoading ? (
                <div className="loading-box">Đang tải biểu đồ...</div>
              ) : historyRows.length > 0 ? (
                <TrendChart
                  title={`Biểu đồ tăng trưởng #${selectedTrend.tag_name}`}
                  description="Đường xanh là lượt xem tăng thêm, đường hồng là tỷ lệ tương tác theo thời gian."
                  labels={historyLabels}
                  dateValues={historyRows.map((row) => row.date || row.collected_at)}
                  enableTimeFilter={true}
                  enableTypeToggle={true}
                  enableSmartAxis={true}
                  type="line"
                  datasets={[
                    {
                      label: "Lượt xem tăng thêm",
                      data: viewGrowthValues,
                      borderColor: "#42FFF6",
                      backgroundColor: "rgba(66, 255, 246, 0.18)",
                      yAxisID: "y",
                      fill: true,
                    },
                    {
                      label: "Tỷ lệ tương tác",
                      data: engagementValues,
                      borderColor: "#FE2062",
                      backgroundColor: "rgba(254, 32, 98, 0.10)",
                      yAxisID: "y1",
                      fill: false,
                    },
                  ]}
                />
              ) : (
                <div className="trend-empty-chart">
                  Hashtag này chưa có dữ liệu trend_history để vẽ biểu đồ.
                </div>
              )}
            </div>
          ) : (
            <div className="trend-empty-chart">
              Chọn một hashtag hoặc bấm “Xem biểu đồ” để xem tốc độ tăng trưởng.
            </div>
          )}
        </div>

        <div className="col-lg-4">
          <div className="card-box h-100">
            <div className="section-header">
              <h5>Top dự đoán LSTM</h5>
              <span>Xếp hạng theo lượt xem tăng thêm dự đoán</span>
            </div>

            {predictedTrends.length > 0 ? (
              <div className="trend-list">
                {predictedTrends.slice(0, 10).map((item, index) => (
                  <div
                    className="trend-list-item"
                    key={item.prediction_id || item.hashtag_id}
                    onClick={() => handleSelectTrend(item)}
                  >
                    <div>
                      <strong>
                        {index + 1}. #{item.tag_name}
                      </strong>
                      <span>Dự đoán cho ngày: {item.predicted_for_date}</span>
                    </div>
                    <b>{formatNumber(item.predicted_growth, { sign: true })}</b>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="Chưa có dữ liệu dự đoán"
                description="Hãy chạy LSTM prediction trong trang Admin Tasks."
              />
            )}
          </div>
        </div>
      </div>

      <div className="card-box">
        <div className="trend-tabs">
          <button
            className={activeTab === "top" ? "active" : ""}
            onClick={() => setActiveTab("top")}
          >
            Hashtag thịnh hành
          </button>

          <button
            className={activeTab === "emerging" ? "active" : ""}
            onClick={() => setActiveTab("emerging")}
          >
            Tăng trưởng nhanh
          </button>

          <button
            className={activeTab === "predicted" ? "active" : ""}
            onClick={() => setActiveTab("predicted")}
          >
            Dự đoán LSTM
          </button>
        </div>

        {currentList.length > 0 ? (
          <div className="table-responsive">
            <table className="table align-middle">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Hashtag</th>
                  <th>{getMetricLabel(activeTab)}</th>
                  <th>Video</th>
                  <th>{activeTab === "predicted" ? "Ngày dự đoán" : "Điểm xu hướng"}</th>
                  <th>Thao tác</th>
                </tr>
              </thead>

              <tbody>
                {currentList.map((item, index) => {
                  const videoCount = getVideoCount(item);
                  const isPredicted = activeTab === "predicted";

                  return (
                    <tr
                      key={item.hashtag_id || item.prediction_id}
                      className={
                        selectedTrend?.hashtag_id === item.hashtag_id
                          ? "clickable-row selected"
                          : "clickable-row"
                      }
                      onClick={() => handleSelectTrend(item)}
                    >
                      <td>{index + 1}</td>

                      <td>
                        <span className="badge-pink">#{item.tag_name}</span>
                      </td>

                      <td>{formatNumber(getTrendValue(item))}</td>

                      <td>{videoCount === null ? "—" : formatNumber(videoCount)}</td>

                      <td>
                        {isPredicted
                          ? item.predicted_for_date || "—"
                          : formatNumber(getTrendScore(item))}
                      </td>

                      <td>
                        <button
                          className="mini-action-btn"
                          onClick={(event) => {
                            event.stopPropagation();
                            handleSelectTrend(item);
                          }}
                        >
                          Xem biểu đồ
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {activeTab === "predicted" && (
              <p className="table-note mt-3">
                Lưu ý: dữ liệu dự đoán được lấy từ bảng predictions. Cột “Lượt xem tăng thêm dự đoán” là predicted_value của LSTM cho ngày tiếp theo.
              </p>
            )}
          </div>
        ) : (
          <EmptyState title="Không có dữ liệu cho mục này" />
        )}
      </div>
    </div>
  );
}

export default Trends;
