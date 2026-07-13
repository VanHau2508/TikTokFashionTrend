import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ExternalLink, PlayCircle } from "lucide-react";

import TrendChart from "../components/TrendChart";
import EmptyState from "../components/EmptyState";
import Pagination from "../components/Pagination";

import {
  getHashtagDetail,
  getHashtagVideos,
} from "../controllers/hashtagController";

function formatNumber(value) {
  return Number(value || 0).toLocaleString("vi-VN");
}

function cleanDescription(text) {
  if (!text) return "Video thời trang TikTok";
  return text.length > 90 ? `${text.slice(0, 90)}...` : text;
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

function getVideoStatusLabel(status) {
  const normalized = String(status || "unknown").toLowerCase();

  if (normalized === "success") return "YOLO success";
  if (normalized === "pending") return "Chờ xử lý";
  if (normalized === "failed") return "Không hợp lệ";
  if (normalized === "processing") return "Đang xử lý";

  return "Chưa xác định";
}

function HashtagDetail() {
  const { hashtagId } = useParams();
  const navigate = useNavigate();

  const [detail, setDetail] = useState(null);
  const [hashtagInfo, setHashtagInfo] = useState(null);
  const [videos, setVideos] = useState([]);

  const [loading, setLoading] = useState(true);
  const [videoLoading, setVideoLoading] = useState(true);

  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const [totalVideos, setTotalVideos] = useState(0);
  const [trendScore, setTrendScore] = useState(0);

  const pageSize = 50;

  useEffect(() => {
    setPage(1);
  }, [hashtagId]);

  useEffect(() => {
    loadDetail();
  }, [hashtagId]);

  useEffect(() => {
    loadHashtagVideos();
  }, [hashtagId, page]);

  const loadDetail = async () => {
    try {
      setLoading(true);

      const response = await getHashtagDetail(hashtagId);
      const result = response.data || response;

      setDetail(result);

      setTrendScore(
        result.trend_score ||
          result.trending_score ||
          result.history?.[result.history.length - 1]?.trend_score ||
          0
      );
    } catch (error) {
      console.error("Hashtag detail error:", error);
      setDetail(null);
    } finally {
      setLoading(false);
    }
  };

  const loadHashtagVideos = async () => {
    try {
      setVideoLoading(true);

      const response = await getHashtagVideos(hashtagId, page, pageSize);
      const result = response.data || response;

      setHashtagInfo(result.hashtag || null);
      setVideos(result.items || []);
      setTotalPages(result.total_pages || 1);
      setTotalVideos(
        result.total ||
          result.hashtag?.total_videos ||
          result.hashtag?.video_count ||
          0
      );
      setTrendScore(
        result.hashtag?.trend_score ||
          result.hashtag?.trending_score ||
          trendScore ||
          0
      );
    } catch (error) {
      console.error("Hashtag videos error:", error);
      setVideos([]);
      setTotalPages(1);
      setTotalVideos(0);
    } finally {
      setVideoLoading(false);
    }
  };

  const displayHashtag = detail?.tag_name || hashtagInfo?.tag_name || "";
  const history = detail?.history || [];

  const relatedHashtags = useMemo(() => {
    const map = {};

    videos.forEach((video) => {
      video.hashtags?.forEach((tag) => {
        if (tag && tag !== displayHashtag) {
          map[tag] = (map[tag] || 0) + 1;
        }
      });
    });

    return Object.entries(map)
      .map(([tag, total]) => ({ tag, total }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 10);
  }, [videos, displayHashtag]);

  const topItems = useMemo(() => {
    const map = {};

    videos.forEach((video) => {
      video.fashion_items?.forEach((item) => {
        map[item] = (map[item] || 0) + 1;
      });
    });

    return Object.entries(map)
      .map(([item, total]) => ({ item, total }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 10);
  }, [videos]);

  const labels = history.map((row) => row.date);
  const viewGrowthValues = history.map((row) => row.view_growth || 0);
  const engagementValues = history.map((row) => row.engagement_rate || 0);

  if (loading) {
    return <div className="loading-box">Đang tải chi tiết hashtag...</div>;
  }

  return (
    <div>
      <h1 className="page-title">#{displayHashtag}</h1>
      <p className="page-subtitle">
        Chi tiết hashtag, biểu đồ tăng trưởng, các item thời trang liên quan và danh sách video thuộc hashtag này.
      </p>

      <div className="hashtag-detail-hero">
        <div>
          <span>Phân tích hashtag</span>
          <h2>Video YOLO success thuộc #{displayHashtag}</h2>
          <p>
            Đang hiển thị {formatNumber(videos.length)} video trong trang này. Tổng cộng{" "}
            {formatNumber(totalVideos)} video.
          </p>
        </div>

        <div className="hashtag-detail-stats">
          <div>
            <span>Tổng video</span>
            <strong>{formatNumber(totalVideos)}</strong>
          </div>

          <div>
            <span>Mốc lịch sử</span>
            <strong>{formatNumber(history.length)}</strong>
          </div>

          <div>
            <span>Điểm xu hướng</span>
            <strong>{formatNumber(trendScore)}</strong>
          </div>
        </div>
      </div>

      <div className="mb-4">
        {history.length > 0 ? (
          <TrendChart
            title={`Biểu đồ lịch sử #${displayHashtag}`}
            description="Đường xanh là lượt xem tăng thêm, đường hồng là tỷ lệ tương tác theo từng ngày."
            labels={labels}
            dateValues={history.map((row) => row.date)}
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
          <EmptyState title="Chưa có dữ liệu lịch sử xu hướng" />
        )}
      </div>

      <div className="row g-3 mb-4">
        <div className="col-lg-6">
          <div className="card-box h-100">
            <div className="section-header">
              <h5>Hashtag liên quan</h5>
              <span>Các hashtag thường xuất hiện cùng trong danh sách video</span>
            </div>

            {relatedHashtags.length > 0 ? (
              <div className="related-chip-list">
                {relatedHashtags.map((item) => (
                  <div className="related-chip" key={item.tag}>
                    <span>#{item.tag}</span>
                    <strong>{item.total}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="Chưa có hashtag liên quan" />
            )}
          </div>
        </div>

        <div className="col-lg-6">
          <div className="card-box h-100">
            <div className="section-header">
              <h5>Item thời trang nổi bật</h5>
              <span>Item được YOLOv8 nhận diện trong danh sách video</span>
            </div>

            {topItems.length > 0 ? (
              <div className="related-chip-list">
                {topItems.map((item) => (
                  <div className="related-chip item" key={item.item}>
                    <span>{item.item}</span>
                    <strong>{item.total}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="Chưa có item thời trang" />
            )}
          </div>
        </div>
      </div>

      <div className="card-box">
        <div className="section-header">
          <h5>Video thuộc hashtag #{displayHashtag}</h5>
          <span>
            Trang {page}/{totalPages}
          </span>
        </div>

        {videoLoading ? (
          <div className="loading-box">Đang tải video...</div>
        ) : videos.length === 0 ? (
          <EmptyState title="Chưa có video cho hashtag này" />
        ) : (
          <>
            <div className="video-grid">
              {videos.map((video) => (
                <div className="video-card" key={video.video_id}>
                  <div className="video-thumb">
                    <div className="video-placeholder">
                      <PlayCircle size={46} />
                      <span>Video thời trang</span>
                    </div>

                    {isValidImageUrl(video.cover_url) && (
                      <img
                        src={video.cover_url}
                        alt={video.description || "Video thời trang"}
                        onError={(event) => {
                          event.currentTarget.style.display = "none";
                        }}
                      />
                    )}

                    <span className="video-status-badge">
                      {getVideoStatusLabel(video.processing_status)}
                    </span>
                  </div>

                  <div className="video-body">
                    <h5>{cleanDescription(video.description)}</h5>

                    <div className="video-tags">
                      {video.hashtags?.slice(0, 4).map((tag, index) => (
                        <span key={`${video.video_id}-${tag}-${index}`}>
                          #{tag}
                        </span>
                      ))}
                    </div>

                    <div className="video-stats video-stats-four">
                      <div>
                        <strong>{formatNumber(video.view_count)}</strong>
                        <span>Lượt xem</span>
                      </div>
                      <div>
                        <strong>{formatNumber(video.like_count)}</strong>
                        <span>Lượt thích</span>
                      </div>
                      <div>
                        <strong>{formatNumber(video.comment_count)}</strong>
                        <span>Bình luận</span>
                      </div>
                      <div>
                        <strong>{formatNumber(video.share_count)}</strong>
                        <span>Chia sẻ</span>
                      </div>
                    </div>

                    <div className="fashion-item-list">
                      {video.fashion_items?.length > 0 ? (
                        video.fashion_items.map((item, index) => (
                          <span key={`${video.video_id}-${item}-${index}`}>
                            {item}
                          </span>
                        ))
                      ) : (
                        <span>Không có item chi tiết</span>
                      )}
                    </div>

                    <div className="video-actions">
                      <button
                        className="mini-action-btn"
                        onClick={() => navigate(`/app/videos/${video.video_id}`)}
                      >
                        Xem chi tiết video
                      </button>

                      <a
                        href={video.video_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="open-link"
                      >
                        Mở trên TikTok <ExternalLink size={16} />
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <Pagination
              page={page}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          </>
        )}
      </div>
    </div>
  );
}

export default HashtagDetail;
