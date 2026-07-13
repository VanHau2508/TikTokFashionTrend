import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ExternalLink,
  PlayCircle,
  RefreshCw,
  Eye,
  Heart,
  MessageCircle,
  Share2,
} from "lucide-react";

import TrendChart from "../components/TrendChart";
import EmptyState from "../components/EmptyState";
import { getVideoEngagementAnalysis } from "../controllers/analyticsController";

const BLACKLIST_TAGS = [
  "fyp",
  "fypシ",
  "foryou",
  "foryoupage",
  "viral",
  "trending",
  "trend",
  "xuhuong",
  "xh",
  "xhh",
  "xhhh",
  "foryouu",
  "fy",
  "douyin",
  "review",
  "capcut",
  "tiktok",
  "viralvideo",
];

function formatNumber(value) {
  return Number(value || 0).toLocaleString("vi-VN");
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(2)}%`;
}

function formatDateTime(value) {
  if (!value) return "";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value).replace("T", " ").slice(0, 16);
  }

  return date.toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isValidImageUrl(url) {
  if (!url) return false;

  const lower = String(url).toLowerCase();

  if (lower.includes("/video/")) return false;
  if (lower.includes("tiktok.com/@")) return false;

  return (
    lower.startsWith("http://") ||
    lower.startsWith("https://") ||
    lower.startsWith("/")
  );
}

function uniqueArray(arr = []) {
  return [...new Set(arr.filter(Boolean))];
}

function cleanVideoTitle(text) {
  if (!text) return "Video thời trang TikTok";

  const cleaned = String(text)
    .replace(/https?:\/\/\S+/g, "")
    .replace(/#[^\s#]+/g, "")
    .replace(/\s+/g, " ")
    .trim();

  if (!cleaned) return "Video thời trang TikTok";

  return cleaned.length > 110 ? `${cleaned.slice(0, 110)}...` : cleaned;
}

function getVisibleHashtags(tags = []) {
  return uniqueArray(tags)
    .map((tag) => String(tag).replace("#", "").trim())
    .filter((tag) => tag && !BLACKLIST_TAGS.includes(tag.toLowerCase()))
    .slice(0, 10);
}

function getTotalEngagement(row = {}) {
  const totalFromDb = Number(row.total_engagement || 0);

  if (totalFromDb > 0) {
    return totalFromDb;
  }

  return (
    Number(row.like_count || 0) +
    Number(row.comment_count || 0) +
    Number(row.share_count || 0)
  );
}

function calculateEngagementRate(row = {}) {
  const explicitRate = row.engagement_rate;

  if (explicitRate !== undefined && explicitRate !== null) {
    return Number(explicitRate || 0);
  }

  const views = Number(row.view_count || 0);

  if (views <= 0) {
    return 0;
  }

  return (getTotalEngagement(row) / views) * 100;
}

function getDelta(current, previous) {
  return Number(current || 0) - Number(previous || 0);
}

function getSafeDelta(current, previous) {
  return Math.max(0, getDelta(current, previous));
}

function getEngagementStatus(latestRate, previousRate) {
  const latest = Number(latestRate || 0);
  const previous = Number(previousRate || 0);
  const delta = latest - previous;

  if (delta > 0.01) {
    return {
      label: "Đang tăng",
      className: "engagement-up",
      color: "#16a34a",
      background: "rgba(22, 163, 74, 0.12)",
      progress: "#16a34a",
      description: `Tăng ${formatPercent(delta)} so với lần ghi nhận trước`,
    };
  }

  if (latest >= 2) {
    return {
      label: "Ổn định",
      className: "engagement-stable",
      color: "#d97706",
      background: "rgba(217, 119, 6, 0.14)",
      progress: "#d97706",
      description: "Tỷ lệ tương tác ở mức trung bình hoặc ổn định",
    };
  }

  return {
    label: "Cần theo dõi",
    className: "engagement-down",
    color: "#dc2626",
    background: "rgba(220, 38, 38, 0.12)",
    progress: "#dc2626",
    description:
      delta < -0.01
        ? `Giảm ${formatPercent(Math.abs(delta))} so với lần ghi nhận trước`
        : "Tỷ lệ tương tác thấp hoặc chưa có dấu hiệu tăng",
  };
}

function MetricCard({ title, value, description, icon: Icon }) {
  return (
    <div className="video-detail-metric-card">
      <div className="engagement-card-top">
        <span className="card-header-mini">{title}</span>

        <span className="metric-icon-soft">
          <Icon size={19} />
        </span>
      </div>

      <strong className="metric-val text-dark">
        {formatNumber(value)}
      </strong>

      <p className="metric-desc">{description}</p>
    </div>
  );
}

function VideoDetailPage() {
  const { videoId } = useParams();
  const navigate = useNavigate();

  const [videoData, setVideoData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    loadVideoDetail();
  }, [videoId]);

  const loadVideoDetail = async () => {
    try {
      setLoading(true);

      const response = await getVideoEngagementAnalysis(videoId);
      const result = response.data || response;

      setVideoData(result?.item || null);
    } catch (error) {
      console.error("Video detail page error:", error);
      setVideoData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSyncData = async () => {
    try {
      setIsSyncing(true);

      const response = await getVideoEngagementAnalysis(videoId);
      const result = response.data || response;

      setVideoData(result?.item || null);
      alert("Đồng bộ dữ liệu thành công!");
    } catch (error) {
      console.error("Lỗi đồng bộ:", error);
      alert("Đồng bộ thất bại, vui lòng thử lại sau.");
    } finally {
      setIsSyncing(false);
    }
  };

  if (loading) {
    return (
      <div className="loading-container">
        <RefreshCw className="spinner" size={24} />
        <p>Đang tải chi tiết video...</p>
      </div>
    );
  }

  if (!videoData) {
    return (
      <EmptyState
        title="Không tìm thấy video"
        description="Video này chưa có dữ liệu hoặc chưa có lịch sử thống kê."
      />
    );
  }

  const latestStats = videoData.latest_stats || {};
  const history = videoData.stats_history || [];

  // Không dùng useMemo ở đây để tránh lỗi thay đổi thứ tự Hooks khi component có return sớm.
  const sortedHistory = [...history].sort(
    (a, b) => new Date(a.collected_at) - new Date(b.collected_at)
  );

  const previousHistory = sortedHistory[sortedHistory.length - 2] || {};

  const labels = sortedHistory.map((row) => formatDateTime(row.collected_at));

  const viewGrowthValues = sortedHistory.map((row, index) => {
    if (index === 0) return 0;
    return getSafeDelta(row.view_count, sortedHistory[index - 1]?.view_count);
  });

  const likeGrowthValues = sortedHistory.map((row, index) => {
    if (index === 0) return 0;
    return getSafeDelta(row.like_count, sortedHistory[index - 1]?.like_count);
  });

  const engagementValues = sortedHistory.map((row) => calculateEngagementRate(row));

  const latestEngagementRate = calculateEngagementRate(latestStats);
  const previousEngagementRate = calculateEngagementRate(previousHistory);

  const hasCover = isValidImageUrl(videoData.cover_url);
  const visibleHashtags = getVisibleHashtags(videoData.hashtags || []);
  const uniqueFashionItems = uniqueArray(videoData.fashion_items || []);

  const engagementStatus = getEngagementStatus(
    latestEngagementRate,
    previousEngagementRate
  );

  const engagementPercent = Math.min(Math.max(latestEngagementRate, 0), 100);

  const isFlatTimeline =
    sortedHistory.length > 1 &&
    viewGrowthValues.every((value) => Number(value || 0) === 0) &&
    likeGrowthValues.every((value) => Number(value || 0) === 0);

  return (
    <div className="video-detail-page">
      <div className="page-header mb-4">
        <button className="back-btn" onClick={() => navigate(-1)}>
          <ArrowLeft size={18} />
          <span>Quay lại</span>
        </button>
      </div>

      <div className="video-detail-hero-pro mb-4">
        <div className="video-detail-cover">
          <div className="video-placeholder">
            <PlayCircle size={40} />
            <span>Video thời trang</span>
          </div>

          {hasCover && (
            <img
              src={videoData.cover_url}
              alt={videoData.description || "Video thời trang"}
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
            />
          )}
        </div>

        <div className="video-detail-content">
          <span className="video-detail-badge">Phân tích tương tác video</span>

          <h1 className="video-detail-title">
            {cleanVideoTitle(videoData.description)}
          </h1>

          <div className="video-tags-container mb-3">
            {visibleHashtags.length > 0 ? (
              visibleHashtags.map((tag, index) => (
                <span className="tag-item" key={`${tag}-${index}`}>
                  #{tag}
                </span>
              ))
            ) : (
              <span className="tag-item">#fashion</span>
            )}
          </div>

          <div className="fashion-item-container mb-4">
            <small className="section-label">
              Vật phẩm thời trang AI nhận diện:
            </small>

            <div className="fashion-item-list">
              {uniqueFashionItems.length > 0 ? (
                uniqueFashionItems.map((item, index) => (
                  <span className="fashion-badge" key={`${item}-${index}`}>
                    {item}
                  </span>
                ))
              ) : (
                <span className="fashion-badge empty">
                  Chưa nhận diện được vật phẩm
                </span>
              )}
            </div>
          </div>

          <div className="video-actions-group">
            <a
              href={videoData.video_url}
              target="_blank"
              rel="noopener noreferrer"
              className="action-btn primary-btn"
            >
              Mở video gốc <ExternalLink size={16} />
            </a>

            <button
              onClick={handleSyncData}
              className={`action-btn secondary-btn ${isSyncing ? "syncing" : ""}`}
              disabled={isSyncing}
            >
              <RefreshCw size={16} className={isSyncing ? "spin-icon" : ""} />
              {isSyncing ? "Đang đồng bộ..." : "Đồng bộ dữ liệu"}
            </button>
          </div>
        </div>
      </div>

      <div className="video-detail-metric-grid mb-4">
        <MetricCard
          title="Lượt xem"
          value={latestStats.view_count}
          description="Tổng lượt xem mới nhất"
          icon={Eye}
        />

        <MetricCard
          title="Lượt thích"
          value={latestStats.like_count}
          description="Lượt thích đồng bộ gần nhất"
          icon={Heart}
        />

        <MetricCard
          title="Bình luận"
          value={latestStats.comment_count}
          description="Số bình luận ghi nhận được"
          icon={MessageCircle}
        />

        <MetricCard
          title="Lượt chia sẻ"
          value={latestStats.share_count}
          description="Số lượt chia sẻ của video"
          icon={Share2}
        />

        <div
          className={`video-detail-metric-card engagement-card-pro ${engagementStatus.className}`}
          style={{
            borderColor: engagementStatus.color,
            background: engagementStatus.background,
          }}
        >
          <div className="engagement-card-top">
            <span className="card-header-mini">Tỷ lệ tương tác</span>

            <span
              className="level-badge"
              style={{
                color: engagementStatus.color,
                background: "rgba(255, 255, 255, 0.72)",
              }}
            >
              {engagementStatus.label}
            </span>
          </div>

          <strong
            className="metric-val"
            style={{ color: engagementStatus.color }}
          >
            {formatPercent(latestEngagementRate)}
          </strong>

          <div className="engagement-progress-bar">
            <div
              className="progress-fill"
              style={{
                width: `${engagementPercent}%`,
                background: engagementStatus.progress,
              }}
            />
          </div>

          <p className="metric-desc">{engagementStatus.description}</p>
        </div>
      </div>

      <div className="chart-wrapper-pro">
        {sortedHistory.length > 0 ? (
          <>
            {isFlatTimeline && (
              <div className="alert alert-warning mb-3" role="alert">
                Các lần đồng bộ hiện tại chưa ghi nhận thay đổi về lượt xem hoặc
                lượt thích, nên biểu đồ tăng trưởng có thể đi ngang. Hãy đồng bộ
                lại sau một khoảng thời gian dài hơn để thấy biến động rõ hơn.
              </div>
            )}

            <TrendChart
              title="Biểu đồ tăng trưởng tương tác video"
              description="Theo dõi lượt xem tăng thêm, lượt thích tăng thêm và tỷ lệ tương tác qua từng lần thu thập."
              labels={labels}
              dateValues={sortedHistory.map((row) => row.collected_at)}
              enableTimeFilter={true}
              enableTypeToggle={false}
              enableSmartAxis={true}
              type="line"
              datasets={[
                {
                  label: "Lượt xem tăng thêm",
                  data: viewGrowthValues,
                  borderColor: "#FE2062",
                  backgroundColor: "rgba(254, 32, 98, 0.08)",
                  yAxisID: "y",
                  fill: true,
                },
                {
                  label: "Lượt thích tăng thêm",
                  data: likeGrowthValues,
                  borderColor: "#42FFF6",
                  backgroundColor: "rgba(66, 255, 246, 0.14)",
                  yAxisID: "y",
                  fill: false,
                },
                {
                  label: "Tỷ lệ tương tác",
                  data: engagementValues,
                  borderColor: "#1F283C",
                  backgroundColor: "transparent",
                  yAxisID: "y1",
                  fill: false,
                },
              ]}
            />
          </>
        ) : (
          <EmptyState title="Video này chưa có dữ liệu thống kê theo thời gian" />
        )}
      </div>
    </div>
  );
}

export default VideoDetailPage;
