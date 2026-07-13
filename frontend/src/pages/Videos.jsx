import React, { useEffect, useState } from "react";
import { ExternalLink, PlayCircle, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";

import {
  getTrendingVideos,
  getFashionItemOptions,
} from "../controllers/videoController";

import EmptyState from "../components/EmptyState";
import Pagination from "../components/Pagination";


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

const PAGE_SIZE = 50;

function formatNumber(value) {
  return Number(value || 0).toLocaleString("vi-VN");
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

function cleanDescription(text) {
  if (!text) return "TikTok Fashion Video";
  return text.length > 90 ? `${text.slice(0, 90)}...` : text;
}

function Videos() {
  const [videos, setVideos] = useState([]);
  const [fashionOptions, setFashionOptions] = useState([]);

  const [loading, setLoading] = useState(true);

  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const [keyword, setKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState("success");
  const [itemFilter, setItemFilter] = useState("all");
  const [sortBy, setSortBy] = useState("views");
  
  const navigate = useNavigate();

  const [meta, setMeta] = useState({
    total: 0,
    total_pages: 1,
    page: 1,
    page_size: PAGE_SIZE,
  });

  useEffect(() => {
    loadFashionOptions();
  }, []);

  useEffect(() => {
    loadVideos();
  }, [page, statusFilter, itemFilter, sortBy]);

  const loadFashionOptions = async () => {
    try {
      const response = await getFashionItemOptions();
      const result = response.data || response;

      setFashionOptions(result || []);
    } catch (error) {
      console.error("Fashion options error:", error);
      setFashionOptions([]);
    }
  };

  const loadVideos = async () => {
    try {
      setLoading(true);

      const response = await getTrendingVideos(page, PAGE_SIZE, {
        search: keyword,
        status: statusFilter,
        item: itemFilter,
        sort_by: sortBy,
      });

      const result = response.data || response;

      setVideos(result.items || []);
      setTotalPages(result.total_pages || 1);

      setMeta({
        total: result.total || 0,
        total_pages: result.total_pages || 1,
        page: result.page || page,
        page_size: result.page_size || PAGE_SIZE,
      });
    } catch (error) {
      console.error("Video page error:", error);
      setVideos([]);
      setTotalPages(1);
      setMeta({
        total: 0,
        total_pages: 1,
        page: 1,
        page_size: PAGE_SIZE,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (event) => {
    event.preventDefault();

    if (page !== 1) {
      setPage(1);
    } else {
      loadVideos();
    }
  };

  if (loading) {
    return <div className="loading-box">Đang tải video thịnh hành...</div>;
  }

  return (
    <div>
      <h1 className="page-title">Video Explorer</h1>
      <p className="page-subtitle">
        Khám phá các video thời trang đã được YOLOv8 nhận diện thành công, lọc theo item, từ khóa và sắp xếp theo chỉ số tương tác.
      </p>

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
          value={statusFilter}
          onChange={(event) => {
            setStatusFilter(event.target.value);
            setPage(1);
          }}
        >
          <option value="success">YOLO success</option>
        </select>

        <select
          value={itemFilter}
          onChange={(event) => {
            setItemFilter(event.target.value);
            setPage(1);
          }}
        >
          <option value="all">Tất cả item</option>
          {fashionOptions.map((item) => (
            <option value={item} key={item}>
              {item}
            </option>
          ))}
        </select>

        <select
          value={sortBy}
          onChange={(event) => {
            setSortBy(event.target.value);
            setPage(1);
          }}
        >
          <option value="views">Sort by views</option>
          <option value="likes">Sort by likes</option>
          <option value="comments">Sort by comments</option>
          <option value="shares">Sort by shares</option>
          <option value="growth">Sort by growth</option>
        </select>
      </div>

      <div className="video-summary-strip">
        <div>
          <span>Video YOLO success</span>
          <strong>{formatNumber(meta.total)}</strong>
        </div>

        <div>
          <span>Đang hiển thị</span>
          <strong>{formatNumber(videos.length)}</strong>
        </div>

        <div>
          <span>YOLO success trong trang</span>
          <strong>
            {formatNumber(
              videos.filter((item) => item.processing_status === "success")
                .length
            )}
          </strong>
        </div>
      </div>

      {videos.length === 0 ? (
        <EmptyState
          title="Không tìm thấy video"
          description="Thử đổi từ khóa, trạng thái hoặc item lọc."
        />
      ) : (
        <>
          <div className="video-grid">
            {videos.map((video) => {
              const visibleTags =
                video.hashtags
                  ?.filter(
                    (tag) =>
                      !BLACKLIST_TAGS.includes(String(tag).toLowerCase())
                  )
                  ?.slice(0, 4) || [];

              const hasValidCover = isValidImageUrl(video.cover_url);

              return (
                <div className="video-card" key={video.video_id}>
                  <div className="video-thumb">
                    <div className="video-placeholder">
                      <PlayCircle size={46} />
                      <span>Fashion Video</span>
                    </div>

                    {hasValidCover && (
                      <img
                        src={video.cover_url}
                        alt={cleanDescription(video.description)}
                        onError={(event) => {
                          event.currentTarget.style.display = "none";
                        }}
                      />
                    )}

                    <span className="video-status-badge">
                      {video.processing_status || "unknown"}
                    </span>
                  </div>

                  <div className="video-body">
                    <h5>{cleanDescription(video.description)}</h5>

                    <div className="video-tags">
                      {visibleTags.length > 0 ? (
                        visibleTags.map((tag, index) => (
                          <span key={`${video.video_id}-${tag}-${index}`}>
                            #{tag}
                          </span>
                        ))
                      ) : (
                        <span>fashion</span>
                      )}
                    </div>

                    <div className="video-growth-box">
                      <div>
                        <span>Trending score</span>
                        <strong>{formatNumber(video.trending_score)}</strong>
                      </div>
                      <div>
                        <span>View growth</span>
                        <strong>+{formatNumber(video.view_growth)}</strong>
                      </div>
                    </div>

                    <div className="video-stats video-stats-four">
                      <div>
                        <strong>{formatNumber(video.view_count)}</strong>
                        <span>Views</span>
                      </div>
                      <div>
                        <strong>{formatNumber(video.like_count)}</strong>
                        <span>Likes</span>
                      </div>
                      <div>
                        <strong>{formatNumber(video.comment_count)}</strong>
                        <span>Comments</span>
                      </div>
                      <div>
                        <strong>{formatNumber(video.share_count)}</strong>
                        <span>Shares</span>
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
                        <span>fashion item</span>
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
              );
            })}
          </div>

          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}

export default Videos;