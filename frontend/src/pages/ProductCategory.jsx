import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useNavigate } from "react-router-dom";

import { Search, PlayCircle, ExternalLink } from "lucide-react";

import { getProductCategoryVideos } from "../controllers/productController";
import EmptyState from "../components/EmptyState";
import VideoDetailModal from "../components/VideoDetailModal";

import Pagination from "../components/Pagination";

const STYLE_FILTERS = [
  {
    key: "all",
    label: "Tất cả",
    keywords: [],
  },
  {
    key: "streetwear",
    label: "Streetwear",
    keywords: ["streetwear", "skate", "skater", "baggy", "oversize"],
  },
  {
    key: "y2k",
    label: "Y2K",
    keywords: ["y2k", "vintage", "retro", "affliction", "jnco"],
  },
  {
    key: "basic",
    label: "Basic",
    keywords: ["basic", "simple", "minimal", "daily", "casual"],
  },
  {
    key: "formal",
    label: "Formal",
    keywords: ["formal", "office", "oldmoney", "polo", "shirt"],
  },
  {
    key: "sporty",
    label: "Sporty",
    keywords: ["sport", "gym", "athletic", "sneaker", "shorts"],
  },
];

function formatNumber(value) {
  const numberValue = Number(value || 0);
  if (!Number.isFinite(numberValue)) return "0";
  return Math.round(numberValue).toLocaleString("vi-VN");
}

function cleanDescription(text) {
  if (!text) return "TikTok Fashion Video";
  return text.length > 90 ? `${text.slice(0, 90)}...` : text;
}

function isValidImageUrl(url) {
  if (!url) return false;

  const lower = url.toLowerCase();

  if (lower.includes("/video/")) return false;
  if (lower.includes("tiktok.com/@")) return false;

  return (
    lower.startsWith("http://") ||
    lower.startsWith("https://") ||
    lower.startsWith("/")
  );
}

function ProductCategory() {
  const { category } = useParams();

  const [data, setData] = useState(null);
  const [keyword, setKeyword] = useState("");
  const [sortBy, setSortBy] = useState("views");
  const [styleFilter, setStyleFilter] = useState("all");
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  

  const [videos, setVideos] = useState([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 50;

  useEffect(() => {
    loadCategory();
  }, [category, page, styleFilter, sortBy]);

  const loadCategory = async () => {
    try {
      setLoading(true);

      const response = await getProductCategoryVideos(category, page, pageSize, {
        style: styleFilter,
        search: keyword,
        sort_by: sortBy,
      });

      const result = response.data || response;

      setData(result);
      setVideos(result.items || []);
      setTotalPages(result.total_pages || 1);
    } catch (error) {
      console.error("Product category error:", error);
      setData(null);
      setVideos([]);
      setTotalPages(1);
    } finally {
      setLoading(false);
    }
  };
    const handleSearchSubmit = (event) => {
      event.preventDefault();

      if (page !== 1) {
        setPage(1);
      } else {
        loadCategory();
      }
    };

  if (loading) {
    return <div className="loading-box">Đang tải sản phẩm...</div>;
  }

  return (
    <div>
      <h1 className="page-title">{data?.label}</h1>
      <p className="page-subtitle">{data?.description}</p>

      <div className="style-filter-bar">
        {STYLE_FILTERS.map((style) => (
          <button
            key={style.key}
            className={styleFilter === style.key ? "active" : ""}
            onClick={() => {
              setStyleFilter(style.key);
              setPage(1);
            }}
          >
            {style.label}
          </button>
        ))}
      </div>

      <div className="video-toolbar">
        <form className="video-search" onSubmit={handleSearchSubmit}>
          <Search size={18} />
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="Tìm theo mô tả, hashtag, item..."
          />
        </form>

        <select
          value={sortBy}
          onChange={(event) => {
            setSortBy(event.target.value);
            setPage(1);
          }}
        >
          <option value="views">Sắp xếp theo lượt xem</option>
          <option value="likes">Sắp xếp theo lượt thích</option>
          <option value="comments">Sắp xếp theo bình luận</option>
          <option value="shares">Sắp xếp theo chia sẻ</option>
        </select>
      </div>

      <div className="video-summary-strip">
        <div>
          <span>Tổng video</span>
          <strong>{formatNumber(data?.total)}</strong>
        </div>

        <div>
          <span>Đang hiển thị</span>
          <strong>{formatNumber(videos.length)}</strong>
        </div>

        <div>
          <span>Danh mục</span>
          <strong>{data?.category}</strong>
        </div>
      </div>

      {videos.length === 0 ? (
        <EmptyState title="Không tìm thấy video trong danh mục này" />
      ) : (
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
                    alt={video.description || "Fashion video"}
                    onError={(event) => {
                      event.currentTarget.style.display = "none";
                    }}
                  />
                )}
              </div>

              <div className="video-body">
                <h5>{cleanDescription(video.description)}</h5>

                <div className="video-tags">
                  {video.hashtags?.slice(0, 4).map((tag, index) => (
                    <span key={`${video.video_id}-${tag}-${index}`}>#{tag}</span>
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
                      <span key={`${video.video_id}-${item}-${index}`}>{item}</span>
                    ))
                  ) : (
                    <span>item thời trang</span>
                  )}
                </div>

                <div className="video-actions">
                  <button
                    className="mini-action-btn"
                    onClick={() => navigate(`/app/videos/${video.video_id}`)}
                  >
                    Chi tiết
                  </button>

                  <a
                    href={video.video_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="open-link"
                  >
                    Mở TikTok <ExternalLink size={16} />
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
      />
      <VideoDetailModal
        video={selectedVideo}
        onClose={() => setSelectedVideo(null)}
      />
    </div>
  );
}

export default ProductCategory;