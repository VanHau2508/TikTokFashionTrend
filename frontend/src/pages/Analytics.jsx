import React, { useEffect, useState } from "react";
import {
  BrainCircuit,
  Hash,
  Shirt,
  BarChart3,
  Activity,
  Sparkles,
  History,
  ArrowUpRight,
  RefreshCw,
} from "lucide-react";

import {
  getFashionKeywordAnalysis,
  getTrendTimeline,
  getEngagementAnalysis,
  getPredictionSummary,
  getPeriodComparison,
  getAnalysisHistory,
} from "../controllers/analyticsController";

import EmptyState from "../components/EmptyState";

function formatNumber(value) {
  return Number(value || 0).toLocaleString("vi-VN");
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(2)}%`;
}

function normalizeResponse(response) {
  return response?.data || response || {};
}

function Analytics() {
  const [loading, setLoading] = useState(true);

  const [keywordData, setKeywordData] = useState(null);
  const [timelineData, setTimelineData] = useState(null);
  const [engagementData, setEngagementData] = useState(null);
  const [predictionData, setPredictionData] = useState(null);
  const [comparisonData, setComparisonData] = useState(null);
  const [historyData, setHistoryData] = useState(null);

  const [periodForm, setPeriodForm] = useState({
    startA: "2026-05-09",
    endA: "2026-05-13",
    startB: "2026-05-14",
    endB: "2026-05-19",
  });

  useEffect(() => {
    loadAnalytics();
  }, []);

  const loadAnalytics = async () => {
    try {
      setLoading(true);

      const [
        keywordsRes,
        timelineRes,
        engagementRes,
        predictionRes,
        comparisonRes,
        historyRes,
      ] = await Promise.all([
        getFashionKeywordAnalysis(20),
        getTrendTimeline({ limit: 5 }),
        getEngagementAnalysis(20),
        getPredictionSummary(20),
        getPeriodComparison({
          startA: periodForm.startA,
          endA: periodForm.endA,
          startB: periodForm.startB,
          endB: periodForm.endB,
          limit: 30,
        }),
        getAnalysisHistory(20),
      ]);

      setKeywordData(normalizeResponse(keywordsRes));
      setTimelineData(normalizeResponse(timelineRes));
      setEngagementData(normalizeResponse(engagementRes));
      setPredictionData(normalizeResponse(predictionRes));
      setComparisonData(normalizeResponse(comparisonRes));
      setHistoryData(normalizeResponse(historyRes));
    } catch (error) {
      console.error("Analytics page error:", error);
    } finally {
      setLoading(false);
    }
  };

  const reloadComparison = async () => {
    try {
      const response = await getPeriodComparison({
        startA: periodForm.startA,
        endA: periodForm.endA,
        startB: periodForm.startB,
        endB: periodForm.endB,
        limit: 30,
      });

      setComparisonData(normalizeResponse(response));
    } catch (error) {
      console.error("Period comparison error:", error);
    }
  };

  const handlePeriodChange = (event) => {
    setPeriodForm({
      ...periodForm,
      [event.target.name]: event.target.value,
    });
  };

  if (loading) {
    return <div className="loading-box">Đang tải dữ liệu phân tích AI...</div>;
  }

  const topHashtags = keywordData?.top_hashtags || [];
  const topItems = keywordData?.top_fashion_items || [];
  const topKeywords = keywordData?.top_keywords || [];
  const timelineItems = timelineData?.items || [];
  const topVideosByEngagement = engagementData?.top_videos_by_engagement || [];
  const topHashtagsByEngagement =
    engagementData?.top_hashtags_by_engagement || [];
  const predictions = predictionData?.items || [];
  const comparisonItems = comparisonData?.items || [];
  const analysisSummary = historyData?.summary || {};
  const latestTrendHistory = historyData?.latest_trend_history || [];
  const latestPredictions = historyData?.latest_predictions || [];

  return (
    <div>
      <div className="analytics-hero">
        <div>
          <span className="eyebrow">AI Analytics Center</span>
          <h1>Phân tích dữ liệu thời trang TikTok</h1>
          <p>
            Tổng hợp các phân tích về hashtag, từ khóa, tương tác, xu hướng theo
            thời gian, dự đoán LSTM và lịch sử phân tích của hệ thống.
          </p>
        </div>

        <button className="btn-primary-pink" onClick={loadAnalytics}>
          <RefreshCw size={18} />
          Làm mới dữ liệu
        </button>
      </div>

      <div className="analytics-grid-4">
        <div className="analytics-metric-card">
          <div className="metric-icon pink">
            <Hash size={22} />
          </div>
          <span>Hashtag thời trang</span>
          <strong>{formatNumber(topHashtags.length)}</strong>
          <p>Top hashtag theo trend_score mới nhất.</p>
        </div>

        <div className="analytics-metric-card">
          <div className="metric-icon cyan">
            <Shirt size={22} />
          </div>
          <span>Fashion items</span>
          <strong>{formatNumber(topItems.length)}</strong>
          <p>Item được YOLO phát hiện nhiều nhất.</p>
        </div>

        <div className="analytics-metric-card">
          <div className="metric-icon navy">
            <Sparkles size={22} />
          </div>
          <span>LSTM Predictions</span>
          <strong>{formatNumber(predictions.length)}</strong>
          <p>Dự đoán view_growth theo model v2.</p>
        </div>

        <div className="analytics-metric-card">
          <div className="metric-icon green">
            <History size={22} />
          </div>
          <span>Lịch sử phân tích</span>
          <strong>{formatNumber(analysisSummary.trend_history_rows)}</strong>
          <p>Số bản ghi trend_history đã lưu.</p>
        </div>
      </div>

      <div className="analytics-section">
        <div className="section-header">
          <div>
            <h5>6. Phân tích từ khóa và hashtag liên quan đến thời trang</h5>
            <span>
              Nguồn: hashtags, video_hashtags, description, fashion_items,
              BLACKLIST_TAGS
            </span>
          </div>
        </div>

        <div className="row g-3">
          <div className="col-lg-4">
            <div className="card-box h-100">
              <div className="mini-section-title">
                <Hash size={18} />
                Top Hashtags
              </div>

              {topHashtags.length === 0 ? (
                <EmptyState title="Chưa có hashtag" />
              ) : (
                <div className="analytics-rank-list">
                  {topHashtags.slice(0, 10).map((item, index) => (
                    <div className="analytics-rank-row" key={item.hashtag_id}>
                      <span className="rank-number">{index + 1}</span>
                      <div>
                        <strong>#{item.tag_name}</strong>
                        <small>
                          {formatNumber(item.view_growth)} growth ·{" "}
                          {formatNumber(item.video_count)} videos
                        </small>
                      </div>
                      <b>{formatNumber(item.trend_score)}</b>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="col-lg-4">
            <div className="card-box h-100">
              <div className="mini-section-title">
                <Shirt size={18} />
                Top Fashion Items
              </div>

              {topItems.length === 0 ? (
                <EmptyState title="Chưa có item" />
              ) : (
                <div className="keyword-chip-cloud">
                  {topItems.map((item) => (
                    <div className="keyword-chip" key={item.item_type}>
                      <span>{item.item_type}</span>
                      <strong>{formatNumber(item.video_count)}</strong>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="col-lg-4">
            <div className="card-box h-100">
              <div className="mini-section-title">
                <BrainCircuit size={18} />
                Top Keywords
              </div>

              {topKeywords.length === 0 ? (
                <EmptyState title="Chưa có keyword" />
              ) : (
                <div className="keyword-chip-cloud">
                  {topKeywords.map((item) => (
                    <div className="keyword-chip" key={item.keyword}>
                      <span>{item.keyword}</span>
                      <strong>{formatNumber(item.count)}</strong>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="analytics-section">
        <div className="section-header">
          <div>
            <h5>7. Phân tích xu hướng theo thời gian</h5>
            <span>
              Nguồn: trend_history.date, view_count, view_growth,
              engagement_rate, trend_score
            </span>
          </div>
        </div>

        {timelineItems.length === 0 ? (
          <EmptyState title="Chưa có dữ liệu timeline" />
        ) : (
          <div className="timeline-insight-grid">
            {timelineItems.map((item) => {
              const history = item.history || [];
              const latest = history[history.length - 1] || {};
              const previous = history[history.length - 2] || {};

              const deltaGrowth =
                Number(latest.view_growth || 0) -
                Number(previous.view_growth || 0);

              return (
                <div className="timeline-insight-card" key={item.hashtag_id}>
                  <div className="timeline-card-header">
                    <h4>#{item.tag_name}</h4>
                    <span>{formatNumber(item.history_points)} points</span>
                  </div>

                  <div className="timeline-main-value">
                    {formatNumber(latest.view_growth)}
                    <small>latest view_growth</small>
                  </div>

                  <div
                    className={
                      deltaGrowth >= 0
                        ? "trend-delta positive"
                        : "trend-delta negative"
                    }
                  >
                    <ArrowUpRight size={16} />
                    {deltaGrowth >= 0 ? "+" : ""}
                    {formatNumber(deltaGrowth)} so với điểm trước
                  </div>

                  <div className="mini-bar-list">
                    {history.slice(-6).map((row) => {
                      const maxGrowth = Math.max(
                        ...history.map((h) => Number(h.view_growth || 0)),
                        1
                      );

                      const width = Math.min(
                        100,
                        (Number(row.view_growth || 0) / maxGrowth) * 100
                      );

                      return (
                        <div className="mini-bar-row" key={row.date}>
                          <span>{row.date}</span>
                          <div>
                            <i style={{ width: `${width}%` }} />
                          </div>
                          <b>{formatNumber(row.view_growth)}</b>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="analytics-section">
        <div className="section-header">
          <div>
            <h5>8. Phân tích mức độ tương tác của video</h5>
            <span>
              Nguồn: video_stats, like/comment/share, engagement_rate
            </span>
          </div>
        </div>

        <div className="row g-3">
          <div className="col-lg-7">
            <div className="card-box h-100">
              <div className="mini-section-title">
                <Activity size={18} />
                Top video theo engagement
              </div>

              {topVideosByEngagement.length === 0 ? (
                <EmptyState title="Chưa có video engagement" />
              ) : (
                <div className="analytics-table-wrap">
                  <table className="table align-middle analytics-table">
                    <thead>
                      <tr>
                        <th>Video</th>
                        <th>Views</th>
                        <th>Likes</th>
                        <th>Comments</th>
                        <th>Engagement</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topVideosByEngagement.slice(0, 10).map((video) => (
                        <tr key={video.video_id}>
                          <td>
                            <strong>
                              {(video.description || "Fashion Video").slice(
                                0,
                                50
                              )}
                              ...
                            </strong>
                            <br />
                            <small>
                              {video.fashion_items?.slice(0, 3).join(", ")}
                            </small>
                          </td>
                          <td>{formatNumber(video.view_count)}</td>
                          <td>{formatNumber(video.like_count)}</td>
                          <td>{formatNumber(video.comment_count)}</td>
                          <td>
                            <span className="badge-cyan">
                              {formatPercent(video.engagement_rate)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          <div className="col-lg-5">
            <div className="card-box h-100">
              <div className="mini-section-title">
                <Hash size={18} />
                Top hashtag theo engagement
              </div>

              <div className="analytics-rank-list">
                {topHashtagsByEngagement.slice(0, 10).map((item, index) => (
                  <div className="analytics-rank-row" key={item.hashtag_id}>
                    <span className="rank-number">{index + 1}</span>
                    <div>
                      <strong>#{item.tag_name}</strong>
                      <small>
                        {formatNumber(item.view_growth)} growth ·{" "}
                        {formatNumber(item.trend_score)} score
                      </small>
                    </div>
                    <b>{formatPercent(item.engagement_rate)}</b>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="analytics-section">
        <div className="section-header">
          <div>
            <h5>13. Dự đoán xu hướng thời trang trong tương lai</h5>
            <span>
              Nguồn: predictions từ LSTM v2, output predicted view_growth
            </span>
          </div>
        </div>

        {predictions.length === 0 ? (
          <EmptyState title="Chưa có prediction từ LSTM v2" />
        ) : (
          <div className="prediction-grid">
            {predictions.slice(0, 12).map((item, index) => (
              <div className="prediction-card" key={item.prediction_id}>
                <span className="prediction-rank">#{index + 1}</span>
                <h4>#{item.tag_name}</h4>
                <strong>{formatNumber(item.predicted_growth)}</strong>
                <p>
                  Dự đoán tăng trưởng view cho ngày{" "}
                  {item.predicted_for_date || "tiếp theo"}.
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="analytics-section">
        <div className="section-header">
          <div>
            <h5>14. So sánh xu hướng giữa các giai đoạn</h5>
            <span>
              So sánh view_growth, trend_score và engagement_rate từ
              trend_history
            </span>
          </div>
        </div>

        <div className="period-filter-card">
          <div>
            <label>Giai đoạn A - từ</label>
            <input
              type="date"
              name="startA"
              value={periodForm.startA}
              onChange={handlePeriodChange}
            />
          </div>

          <div>
            <label>Giai đoạn A - đến</label>
            <input
              type="date"
              name="endA"
              value={periodForm.endA}
              onChange={handlePeriodChange}
            />
          </div>

          <div>
            <label>Giai đoạn B - từ</label>
            <input
              type="date"
              name="startB"
              value={periodForm.startB}
              onChange={handlePeriodChange}
            />
          </div>

          <div>
            <label>Giai đoạn B - đến</label>
            <input
              type="date"
              name="endB"
              value={periodForm.endB}
              onChange={handlePeriodChange}
            />
          </div>

          <button className="btn-primary-pink" onClick={reloadComparison}>
            So sánh
          </button>
        </div>

        {comparisonItems.length === 0 ? (
          <EmptyState title="Chưa có dữ liệu so sánh" />
        ) : (
          <div className="analytics-table-wrap">
            <table className="table align-middle analytics-table">
              <thead>
                <tr>
                  <th>Hashtag</th>
                  <th>Growth A</th>
                  <th>Growth B</th>
                  <th>Δ Growth</th>
                  <th>Δ Engagement</th>
                  <th>Δ Trend Score</th>
                </tr>
              </thead>
              <tbody>
                {comparisonItems.slice(0, 20).map((item) => (
                  <tr key={item.hashtag_id}>
                    <td>
                      <strong>#{item.tag_name}</strong>
                    </td>
                    <td>{formatNumber(item.period_a?.total_view_growth)}</td>
                    <td>{formatNumber(item.period_b?.total_view_growth)}</td>
                    <td>
                      <span
                        className={
                          item.delta_total_view_growth >= 0
                            ? "badge-green"
                            : "badge-red"
                        }
                      >
                        {item.delta_total_view_growth >= 0 ? "+" : ""}
                        {formatNumber(item.delta_total_view_growth)}
                      </span>
                    </td>
                    <td>{formatPercent(item.delta_engagement_rate)}</td>
                    <td>{formatNumber(item.delta_trend_score)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="analytics-section">
        <div className="section-header">
          <div>
            <h5>15. Lưu và truy xuất lịch sử phân tích</h5>
            <span>
              Nguồn: trend_history, predictions, crawler_jobs, ai_analysis
            </span>
          </div>
        </div>

        <div className="analytics-grid-4 mb-4">
          <div className="analytics-metric-card">
            <span>Trend history</span>
            <strong>{formatNumber(analysisSummary.trend_history_rows)}</strong>
            <p>Bản ghi xu hướng theo ngày.</p>
          </div>

          <div className="analytics-metric-card">
            <span>Predictions</span>
            <strong>{formatNumber(analysisSummary.prediction_rows)}</strong>
            <p>Lịch sử dự đoán LSTM.</p>
          </div>

          <div className="analytics-metric-card">
            <span>Crawler jobs</span>
            <strong>{formatNumber(analysisSummary.crawler_job_rows)}</strong>
            <p>Lịch sử tác vụ crawler/sync.</p>
          </div>

          <div className="analytics-metric-card">
            <span>AI analysis</span>
            <strong>{formatNumber(analysisSummary.ai_analysis_rows)}</strong>
            <p>Lịch sử phân tích AI nếu có.</p>
          </div>
        </div>

        <div className="row g-3">
          <div className="col-lg-6">
            <div className="card-box h-100">
              <div className="mini-section-title">
                <BarChart3 size={18} />
                Trend history mới nhất
              </div>

              <div className="analytics-rank-list">
                {latestTrendHistory.slice(0, 10).map((item, index) => (
                  <div
                    className="analytics-rank-row"
                    key={`${item.hashtag_id}-${item.date}-${index}`}
                  >
                    <span className="rank-number">{index + 1}</span>
                    <div>
                      <strong>#{item.tag_name}</strong>
                      <small>{item.date}</small>
                    </div>
                    <b>{formatNumber(item.trend_score)}</b>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="col-lg-6">
            <div className="card-box h-100">
              <div className="mini-section-title">
                <Sparkles size={18} />
                Prediction mới nhất
              </div>

              <div className="analytics-rank-list">
                {latestPredictions.slice(0, 10).map((item, index) => (
                  <div
                    className="analytics-rank-row"
                    key={`${item.prediction_id}-${index}`}
                  >
                    <span className="rank-number">{index + 1}</span>
                    <div>
                      <strong>#{item.tag_name}</strong>
                      <small>{item.model_version}</small>
                    </div>
                    <b>{formatNumber(item.predicted_value)}</b>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Analytics;