import React, { useEffect, useState } from "react";
import {
  Video,
  Tags,
  BrainCircuit,
  CheckCircle,
  TrendingUp,
  Sparkles,
  Shirt,
} from "lucide-react";

import StatCard from "../components/StatCard";
import TrendChart from "../components/TrendChart";
import EmptyState from "../components/EmptyState";
import InsightCard from "../components/InsightCard";

import { getDashboardSummary } from "../controllers/dashboardController";

import {
  getTopTrends,
  getPredictedTrends,
  getEmergingTrends,
  getTrendHistory,
} from "../controllers/trendController";

import { getTopFashionItems } from "../controllers/videoController";
import PageHeader from "../components/PageHeader";
import SkeletonCard from "../components/SkeletonCard";

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

function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [topTrends, setTopTrends] = useState([]);
  const [predictedTrends, setPredictedTrends] = useState([]);
  const [emergingTrends, setEmergingTrends] = useState([]);
  const [fashionItems, setFashionItems] = useState([]);
  const [growthHistory, setGrowthHistory] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      setLoading(true);

      const [summaryResult, topResult, predictedResult, emergingResult, fashionResult] =
        await Promise.allSettled([
          getDashboardSummary(),
          getTopTrends(8),
          getPredictedTrends(8),
          getEmergingTrends(8, 5),
          getTopFashionItems(8),
        ]);

      const summaryData =
        summaryResult.status === "fulfilled" ? summaryResult.value : null;

      const topData =
        topResult.status === "fulfilled" ? topResult.value || [] : [];

      const predictedData =
        predictedResult.status === "fulfilled" ? predictedResult.value || [] : [];

      const emergingData =
        emergingResult.status === "fulfilled" ? emergingResult.value || [] : [];

      const fashionData =
        fashionResult.status === "fulfilled" ? fashionResult.value || [] : [];

      setSummary(summaryData);
      setTopTrends(topData);
      setPredictedTrends(predictedData);
      setEmergingTrends(emergingData);
      setFashionItems(fashionData);

      if (topData?.length > 0) {
        const historyRes = await getTrendHistory(topData[0].hashtag_id);
        setGrowthHistory(historyRes);
      } else {
        setGrowthHistory(null);
      }
    } catch (error) {
      console.error("Dashboard error:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div>
        <div className="skeleton-page-header" />
        <div className="row g-3 mb-4">
          <div className="col-md-3">
            <SkeletonCard />
          </div>
          <div className="col-md-3">
            <SkeletonCard />
          </div>
          <div className="col-md-3">
            <SkeletonCard />
          </div>
          <div className="col-md-3">
            <SkeletonCard />
          </div>
        </div>
        <div className="skeleton-chart" />
      </div>
    );
  }

  const topTrend = topTrends[0];
  const bestPrediction = predictedTrends[0];
  const bestFashionItem = fashionItems[0];

  const predictedLabels = predictedTrends.map((item) => `#${item.tag_name}`);
  const predictedValues = predictedTrends.map(
    (item) => item.predicted_growth || 0
  );

  const fashionLabels = fashionItems.map((item) => item.item_type);
  const fashionValues = fashionItems.map((item) => item.total || 0);

  const growthRows = growthHistory?.history || [];
  const growthLabels = growthRows.map((row) => row.date);
  const viewGrowthValues = growthRows.map((row) => row.view_growth || 0);
  const viewCountValues = growthRows.map((row) => row.view_count || 0);

  return (
    <div>
      <PageHeader
        title="Tổng quan hệ thống"
        subtitle="Theo dõi dữ liệu TikTok, kết quả YOLOv8 và dự đoán LSTM."
        badge="Phân tích xu hướng thời trang TikTok bằng AI"
        onRefresh={loadDashboard}
      />

      {/* 2. Nhóm chỉ số tổng quan */}
      <div className="row g-3 mb-4">
        <div className="col-md-3">
          <StatCard
            title="Video trong phạm vi"
            value={summary?.total_videos}
            icon={Video}
            description="Video thuộc phạm vi phân tích 2026"
            accent="pink"
          />
        </div>

        <div className="col-md-3">
          <StatCard
            title="Video thời trang hợp lệ"
            value={summary?.success_videos}
            icon={CheckCircle}
            description="Video YOLO success dùng cho thống kê xu hướng"
            accent="cyan"
          />
        </div>

        <div className="col-md-3">
          <StatCard
            title="Hashtag"
            value={summary?.total_hashtags}
            icon={Tags}
            description="Hashtag đã ghi nhận trong hệ thống"
            accent="navy"
          />
        </div>

        <div className="col-md-3">
          <StatCard
            title="Dự đoán LSTM"
            value={summary?.total_predictions}
            icon={BrainCircuit}
            description="Kết quả dự đoán view_growth theo hashtag"
            accent="pink"
          />
        </div>
      </div>

      {/* 3. Nhóm insight nhanh */}
      <div className="insight-grid mb-4">
        <InsightCard
          label="Hashtag nổi bật"
          title={topTrend ? `#${topTrend.tag_name}` : "Chưa có dữ liệu"}
          value={topTrend ? formatNumber(topTrend.view_count) : "0"}
          description="Hashtag có tổng lượt xem cao nhất trong kỳ phân tích gần nhất."
          icon={TrendingUp}
          accent="pink"
        />

        <InsightCard
          label="Dự đoán LSTM"
          title={
            bestPrediction ? `#${bestPrediction.tag_name}` : "Chưa có dự đoán"
          }
          value={
            bestPrediction ? formatNumber(bestPrediction.predicted_growth) : "0"
          }
          description="Hashtag có lượt xem tăng thêm dự đoán cao nhất."
          icon={Sparkles}
          accent="cyan"
        />

        <InsightCard
          label="Vật phẩm thời trang"
          title={bestFashionItem?.item_type || "Chưa có item"}
          value={bestFashionItem ? formatNumber(bestFashionItem.total) : "0"}
          description="Item thời trang được YOLOv8 phát hiện nhiều nhất."
          icon={Shirt}
          accent="navy"
        />
      </div>

      {/* 4. Xu hướng hiện tại */}
      <div className="row g-3 mb-4">
        <div className="col-lg-6">
          <div className="card-box h-100">
            <div className="section-header">
              <h5>Hashtag thịnh hành</h5>
              <span>Xếp hạng theo tổng lượt xem</span>
            </div>

            {topTrends.length > 0 ? (
              <div className="table-responsive">
                <table className="table align-middle">
                  <thead>
                    <tr>
                      <th>Hashtag</th>
                      <th>Lượt xem</th>
                      <th>Video</th>
                      <th>Tương tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topTrends.slice(0, 5).map((item) => (
                      <tr key={item.hashtag_id}>
                        <td>
                          <span className="badge-pink">#{item.tag_name}</span>
                        </td>
                        <td>{formatNumber(item.view_count)}</td>
                        <td>{formatNumber(item.video_count)}</td>
                        <td>{Number(item.engagement_rate || 0).toFixed(2)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState title="Chưa có dữ liệu hashtag thịnh hành" />
            )}
          </div>
        </div>

        <div className="col-lg-6">
          <div className="card-box h-100">
            <div className="section-header">
              <h5>Xu hướng tăng trưởng nhanh</h5>
              <span>Xếp hạng theo view growth và trend score</span>
            </div>

            {emergingTrends.length > 0 ? (
              <div className="table-responsive">
                <table className="table align-middle">
                  <thead>
                    <tr>
                      <th>Hashtag</th>
                      <th>Tăng trưởng</th>
                      <th>Video</th>
                      <th>Điểm xu hướng</th>
                    </tr>
                  </thead>
                  <tbody>
                    {emergingTrends.slice(0, 5).map((item) => (
                      <tr key={item.hashtag_id}>
                        <td>
                          <span className="badge-pink">#{item.tag_name}</span>
                        </td>
                        <td>{formatNumber(item.view_growth)}</td>
                        <td>{formatNumber(item.video_count)}</td>
                        <td>{Number(item.trend_score || 0).toFixed(0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                title="Chưa có xu hướng tăng trưởng nhanh"
                description="Dữ liệu sẽ xuất hiện khi lượt xem tăng thêm hoặc điểm xu hướng tăng ở kỳ phân tích gần nhất."
              />
            )}
          </div>
        </div>
      </div>

      {/* 5. Dự đoán LSTM */}
      <div className="row g-3 mb-4">
        <div className="col-lg-8">
          {predictedTrends.length > 0 ? (
            <TrendChart
              title="Top xu hướng được LSTM dự đoán"
              description="Xếp hạng hashtag theo view growth dự đoán, không phải tổng lượt xem dự đoán."
              type="bar"
              labels={predictedLabels}
              datasets={[
                {
                  label: "Lượt xem tăng thêm dự đoán",
                  data: predictedValues,
                  backgroundColor: "rgba(254, 32, 98, 0.75)",
                  borderRadius: 8,
                },
              ]}
            />
          ) : (
            <EmptyState
              title="Chưa có dữ liệu dự đoán"
              description="Hãy chạy LSTM Prediction để lưu kết quả vào bảng predictions."
            />
          )}
        </div>

        <div className="col-lg-4">
          <div className="card-box h-100">
            <div className="section-header">
              <h5>Top 5 dự đoán LSTM</h5>
              <span>View growth dự đoán</span>
            </div>

            {predictedTrends.length > 0 ? (
              <div className="ranking-list">
                {predictedTrends.slice(0, 5).map((item, index) => (
                  <div className="ranking-item" key={item.prediction_id}>
                    <div className="rank-number">{index + 1}</div>
                    <div>
                      <strong>#{item.tag_name}</strong>
                      <span>Dự đoán cho ngày {item.predicted_for_date}</span>
                    </div>
                    <b>{formatNumber(item.predicted_growth, { sign: true })}</b>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="Chưa có xếp hạng dự đoán" />
            )}
          </div>
        </div>
      </div>

      {/* 6. Phân tích theo thời gian */}
      <div className="row g-3 mb-4">
        <div className="col-12">
          {growthRows.length > 0 ? (
            <TrendChart
              title={
                growthHistory
                  ? `Biểu đồ tăng trưởng #${growthHistory.tag_name}`
                  : "Biểu đồ tăng trưởng hashtag"
              }
              description="Đường hồng là tổng lượt xem tích lũy, đường xanh là lượt xem tăng thêm thực tế theo từng ngày."
              labels={growthLabels}
              dateValues={growthRows.map((row) => row.date)}
              enableTimeFilter={true}
              enableTypeToggle={true}
              enableSmartAxis={true}
              type="line"
              datasets={[
                {
                  label: "Tổng lượt xem",
                  data: viewCountValues,
                  borderColor: "#FE2062",
                  backgroundColor: "rgba(254, 32, 98, 0.12)",
                },
                {
                  label: "Lượt xem tăng thêm",
                  data: viewGrowthValues,
                  borderColor: "#42FFF6",
                  backgroundColor: "rgba(66, 255, 246, 0.18)",
                },
              ]}
            />
          ) : (
            <EmptyState title="Chưa có dữ liệu tăng trưởng theo thời gian" />
          )}
        </div>
      </div>

      {/* 7. YOLOv8 */}
      <div className="row g-3">
        <div className="col-12">
          {fashionItems.length > 0 ? (
            <TrendChart
              title="Top vật phẩm thời trang YOLOv8"
              description="Thống kê các item thời trang được YOLOv8 phát hiện nhiều nhất trong video."
              type="bar"
              labels={fashionLabels}
              datasets={[
                {
                  label: "Số lần phát hiện",
                  data: fashionValues,
                  backgroundColor: "rgba(66, 255, 246, 0.8)",
                  borderRadius: 8,
                },
              ]}
            />
          ) : (
            <EmptyState
              title="Chưa có vật phẩm thời trang"
              description="Hãy chạy YOLOv8 để lưu kết quả nhận diện vào bảng fashion_items."
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
