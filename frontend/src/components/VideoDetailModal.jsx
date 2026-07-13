import React, { useEffect, useState } from "react";
import { X, ExternalLink, PlayCircle, TrendingUp, Activity, Eye } from "lucide-react";
import TrendChart from "./TrendChart";
import { getVideoHistory } from "../controllers/videoController";

function formatNumber(value) {
  return Number(value || 0).toLocaleString("vi-VN");
}

function getTrendStatusLabel(status) {
  if (status === "increasing") return "Đang tăng trưởng";
  if (status === "slowing") return "Tăng chậm lại";
  if (status === "stable") return "Ổn định / ngừng tăng";
  if (status === "not_enough_data") return "Chưa đủ dữ liệu";
  return "Không xác định";
}

function getTrendStatusClass(status) {
  if (status === "increasing") return "trend-status increasing";
  if (status === "slowing") return "trend-status slowing";
  if (status === "stable") return "trend-status stable";
  return "trend-status unknown";
}

function VideoDetailModal({ video, onClose }) {
  const [historyData, setHistoryData] = useState(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    if (video?.video_id) {
      loadVideoHistory(video.video_id);
    }
  }, [video]);

  const loadVideoHistory = async (videoId) => {
    try {
      setLoadingHistory(true);
      const data = await getVideoHistory(videoId);
      setHistoryData(data);
    } catch (error) {
      console.error("Video history error:", error);
      setHistoryData(null);
    } finally {
      setLoadingHistory(false);
    }
  };

  if (!video) return null;

  const history = historyData?.history || [];

  const labels = history.map((row) => {
    if (!row.collected_at) return "";
    return new Date(row.collected_at).toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  });

  const viewCountValues = history.map((row) => row.view_count || 0);
  const viewGrowthValues = history.map((row) => row.view_growth || 0);
  const engagementValues = history.map((row) =>
    Number(row.engagement_rate || 0).toFixed(2)
  );

  return (
    <div className="modal-backdrop-custom" onClick={onClose}>
      <div className="video-modal video-modal-wide" onClick={(event) => event.stopPropagation()}>
        <button className="modal-close-btn" onClick={onClose}>
          <X size={20} />
        </button>

        <div className="video-modal-visual">
          <PlayCircle size={58} />
          <span>Fashion Video Preview</span>
        </div>

        <div className="video-modal-content">
          <div className="section-header">
            <h5>Chi tiết video</h5>
            <span className={getTrendStatusClass(historyData?.trend_status)}>
              {getTrendStatusLabel(historyData?.trend_status)}
            </span>
          </div>

          <h3>{video.description || "TikTok Fashion Video"}</h3>

          <p className="video-analysis-text">
            {historyData?.analysis_text ||
              "Hệ thống đang phân tích lịch sử tăng trưởng của video này."}
          </p>

          <div className="video-tags mb-3">
            {video.hashtags?.slice(0, 8).map((tag) => (
              <span key={tag}>#{tag}</span>
            ))}
          </div>

          <div className="modal-stat-grid">
            <div>
              <span>Views</span>
              <strong>{formatNumber(video.view_count)}</strong>
            </div>
            <div>
              <span>Likes</span>
              <strong>{formatNumber(video.like_count)}</strong>
            </div>
            <div>
              <span>Comments</span>
              <strong>{formatNumber(video.comment_count)}</strong>
            </div>
            <div>
              <span>Shares</span>
              <strong>{formatNumber(video.share_count)}</strong>
            </div>
          </div>

          <div className="video-insight-row">
            <div>
              <Eye size={18} />
              <span>View growth gần nhất</span>
              <strong>{formatNumber(historyData?.latest_view_growth)}</strong>
            </div>

            <div className="trend-reason-box">
            <h5>Lý do được xếp thịnh hành</h5>
            <p>
                Video được đánh giá dựa trên tăng trưởng mới nhất của lượt xem, lượt thích,
                bình luận và chia sẻ. Điểm thịnh hành hiện tại là{" "}
                <strong>{formatNumber(video.trending_score)}</strong>.
            </p>
            </div>

            <div>
              <TrendingUp size={18} />
              <span>Growth kỳ trước</span>
              <strong>{formatNumber(historyData?.previous_view_growth)}</strong>
            </div>

            <div>
              <Activity size={18} />
              <span>History points</span>
              <strong>{formatNumber(historyData?.history_points)}</strong>
            </div>
          </div>

          <div className="fashion-item-list mt-3">
            {video.fashion_items?.length > 0 ? (
              video.fashion_items.map((item) => <span key={item}>{item}</span>)
            ) : (
              <span>fashion item</span>
            )}
          </div>

          <div className="video-history-chart mt-4">
            {loadingHistory ? (
              <div className="loading-box small">Đang tải biểu đồ tăng trưởng...</div>
            ) : history.length >= 2 ? (
              <TrendChart
                title="Biểu đồ tăng trưởng video"
                labels={labels}
                datasets={[
                  {
                    label: "View count",
                    data: viewCountValues,
                    borderColor: "#FE2062",
                    backgroundColor: "rgba(254, 32, 98, 0.12)",
                    tension: 0.35,
                  },
                  {
                    label: "View growth",
                    data: viewGrowthValues,
                    borderColor: "#42FFF6",
                    backgroundColor: "rgba(66, 255, 246, 0.18)",
                    tension: 0.35,
                  },
                  {
                    label: "Engagement rate",
                    data: engagementValues,
                    borderColor: "#1F283C",
                    backgroundColor: "rgba(31, 40, 60, 0.08)",
                    tension: 0.35,
                  },
                ]}
              />
            ) : (
              <div className="video-no-history">
                Chưa đủ dữ liệu lịch sử để vẽ biểu đồ. Cần ít nhất 2 lần sync video stats.
              </div>
            )}
          </div>

          <a
            href={video.video_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary-pink modal-open-link"
          >
            Mở TikTok gốc <ExternalLink size={16} />
          </a>
        </div>
      </div>
    </div>
  );
}

export default VideoDetailModal;