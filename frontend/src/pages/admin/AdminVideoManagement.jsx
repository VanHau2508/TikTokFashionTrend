import React, { useEffect, useMemo, useState } from "react";
import {
  Archive,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Eye,
  Filter,
  Image as ImageIcon,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import toast from "react-hot-toast";

import {
  archiveAdminVideos,
  getAdminFashionItemOptions,
  getAdminVideoCoverUpdater,
  getAdminVideoDetail,
  getAdminVideos,
  getAdminVideoSummary,
  hardDeleteAdminVideos,
  markAdminVideosScope,
  resetAdminVideosForYolo,
  startAdminVideoCoverUpdater,
} from "../../controllers/admin/adminVideoController";
import { runProcessYolo } from "../../controllers/admin/adminTaskController";

const DEFAULT_FILTERS = {
  search: "",
  status: "all",
  scope: "in_scope",
  hashtag: "",
  item: "",
  sort_by: "published_at",
  sort_order: "desc",
  page_size: 50,
};

const STATUS_OPTIONS = [
  { value: "all", label: "Tất cả" },
  { value: "success", label: "Hợp lệ" },
  { value: "failed_no_fashion", label: "Không phát hiện thời trang" },
  { value: "failed_no_frame", label: "Lỗi lấy khung hình" },
  { value: "uncertain", label: "Chưa chắc chắn" },
  { value: "pending", label: "Đang chờ" },
  { value: "error", label: "Lỗi xử lý" },
];

const SCOPE_OPTIONS = [
  { value: "in_scope", label: "Trong phạm vi" },
  { value: "out_scope", label: "Ngoài phạm vi" },
  { value: "all", label: "Tất cả video" },
];

const SORT_OPTIONS = [
  { value: "published_at", label: "Ngày đăng" },
  { value: "views", label: "Lượt xem" },
  { value: "video_id", label: "Video mới thêm" },
  { value: "status", label: "Trạng thái" },
];

function formatNumber(value) {
  return Number(value || 0).toLocaleString("vi-VN");
}

function formatDate(value) {
  if (!value) return "Chưa có";
  return new Date(value).toLocaleString("vi-VN");
}

function isValidImageUrl(url) {
  if (!url) return false;
  const lower = String(url).toLowerCase();

  if (lower.includes("/video/")) return false;
  if (lower.includes("tiktok.com/@")) return false;

  return lower.startsWith("http://") || lower.startsWith("https://") || lower.startsWith("/");
}

function statusClass(status) {
  if (!status) return "unknown";
  if (status.includes("failed")) return status;
  return status;
}

function compactText(text, fallback = "Không có mô tả") {
  if (!text) return fallback;
  return text;
}

function ChipList({ items = [], type = "tag", limit = 3 }) {
  const normalized = (items || []).filter(Boolean);
  const visible = normalized.slice(0, limit);
  const more = normalized.length - visible.length;

  if (normalized.length === 0) {
    return <span className="admin-video-empty-text">Không có</span>;
  }

  return (
    <div className="admin-video-chip-list">
      {visible.map((item, index) => (
        <span className={`admin-video-chip ${type}`} key={`${item}-${index}`}>
          {type === "tag" ? `#${item}` : item}
        </span>
      ))}

      {more > 0 && <span className="admin-video-chip more">+{more}</span>}
    </div>
  );
}

function VideoCover({ video }) {
  if (!isValidImageUrl(video?.cover_url)) {
    return (
      <div className="admin-video-cover-box empty">
        <ImageIcon size={18} />
        <span>Chưa có ảnh</span>
      </div>
    );
  }

  return (
    <div className="admin-video-cover-box">
      {video.cover_url ? (
        <img
            src={video.cover_url}
            alt="Ảnh bìa video"
            onError={(event) => {
            event.currentTarget.style.display = "none";
            const fallback = event.currentTarget.nextElementSibling;
            if (fallback) fallback.style.display = "flex";
            }}
        />
        ) : null}

        <div
        className="admin-video-cover-placeholder"
        style={{ display: video.cover_url ? "none" : "flex" }}
        >
        <span>Chưa có ảnh</span>
        </div>
    </div>
  );
}

function AdminVideoManagement() {
  const [summary, setSummary] = useState(null);
  const [videos, setVideos] = useState([]);
  const [meta, setMeta] = useState({
    page: 1,
    page_size: DEFAULT_FILTERS.page_size,
    total: 0,
    total_pages: 1,
  });

  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [draftFilters, setDraftFilters] = useState(DEFAULT_FILTERS);

  const [fashionOptions, setFashionOptions] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [coverTask, setCoverTask] = useState(null);
  const [yoloTaskStarting, setYoloTaskStarting] = useState(false);

  const selectedCount = selectedIds.length;

  const allVisibleSelected = useMemo(() => {
    if (videos.length === 0) return false;
    return videos.every((video) => selectedIds.includes(video.video_id));
  }, [videos, selectedIds]);

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    loadVideos();
  }, [
    page,
    filters.search,
    filters.status,
    filters.scope,
    filters.hashtag,
    filters.item,
    filters.sort_by,
    filters.sort_order,
    filters.page_size,
  ]);

  useEffect(() => {
    if (!coverTask?.task_id) return;
    if (!["queued", "running"].includes(coverTask.status)) return;

    const timer = setInterval(async () => {
      try {
        const task = await getAdminVideoCoverUpdater(coverTask.task_id);
        setCoverTask(task);

        if (["completed", "failed"].includes(task.status)) {
          clearInterval(timer);

          if (task.status === "completed") {
            toast.success("Đã hoàn tất cập nhật ảnh bìa.");
            await loadVideos();
            await loadSummary();
          } else {
            toast.error(task.error || "Cập nhật ảnh bìa thất bại.");
          }
        }
      } catch (error) {
        clearInterval(timer);
      }
    }, 2500);

    return () => clearInterval(timer);
  }, [coverTask?.task_id, coverTask?.status]);

  const loadInitialData = async () => {
    await Promise.all([loadSummary(), loadFashionOptions()]);
  };

  const loadSummary = async () => {
    try {
      const data = await getAdminVideoSummary();
      setSummary(data?.data || data);
    } catch (error) {
      console.error("Admin video summary error:", error);
    }
  };

  const loadFashionOptions = async () => {
    try {
      const data = await getAdminFashionItemOptions();
      setFashionOptions(data?.data || data || []);
    } catch (error) {
      console.error("Fashion options error:", error);
      setFashionOptions([]);
    }
  };

  const loadVideos = async () => {
    try {
      setLoading(true);

      const data = await getAdminVideos({
        page,
        page_size: filters.page_size,
        search: filters.search,
        status: filters.status,
        scope: filters.scope,
        hashtag: filters.hashtag,
        item: filters.item,
        sort_by: filters.sort_by,
        sort_order: filters.sort_order,
      });

      const result = data?.data || data;

      setVideos(result.items || []);
      setMeta({
        page: result.page || page,
        page_size: result.page_size || filters.page_size,
        total: result.total || 0,
        total_pages: result.total_pages || 1,
      });
      setSelectedIds([]);
    } catch (error) {
      console.error("Admin videos load error:", error);
      toast.error("Không thể tải danh sách video.");
      setVideos([]);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key, value) => {
    setDraftFilters((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleApplyFilters = (event) => {
    event?.preventDefault?.();
    setPage(1);
    setFilters({ ...draftFilters });
  };

  const handleResetFilters = () => {
    setDraftFilters(DEFAULT_FILTERS);
    setFilters(DEFAULT_FILTERS);
    setPage(1);
  };

  const toggleSelected = (videoId) => {
    setSelectedIds((prev) =>
      prev.includes(videoId)
        ? prev.filter((id) => id !== videoId)
        : [...prev, videoId]
    );
  };

  const toggleSelectAllVisible = () => {
    if (allVisibleSelected) {
      setSelectedIds([]);
      return;
    }

    setSelectedIds(videos.map((video) => video.video_id));
  };

  const requireSelection = () => {
    if (selectedIds.length === 0) {
      toast.error("Vui lòng chọn ít nhất một video.");
      return false;
    }

    return true;
  };

  const handleViewDetail = async (videoId) => {
    try {
      setDetailLoading(true);
      const data = await getAdminVideoDetail(videoId);
      setSelectedDetail(data?.data || data);
    } catch (error) {
      toast.error("Không thể tải chi tiết video.");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleResetYolo = async () => {
    if (!requireSelection()) return;

    if (!window.confirm(`Đưa ${selectedIds.length} video về trạng thái chờ YOLO?`)) return;

    try {
      const result = await resetAdminVideosForYolo(selectedIds, true);
      toast.success(result.message || "Đã reset YOLO.");
      await loadVideos();
      await loadSummary();
    } catch (error) {
      toast.error("Reset YOLO thất bại.");
    }
  };

  const handleMarkInScope = async () => {
    if (!requireSelection()) return;

    try {
      const result = await markAdminVideosScope(selectedIds, true, null);
      toast.success(result.message || "Đã đưa video vào phạm vi.");
      await loadVideos();
      await loadSummary();
    } catch (error) {
      toast.error("Cập nhật phạm vi thất bại.");
    }
  };

  const handleArchive = async () => {
    if (!requireSelection()) return;

    if (!window.confirm(`Ẩn ${selectedIds.length} video khỏi pipeline chính?`)) return;

    try {
      const result = await archiveAdminVideos(selectedIds);
      toast.success(result.message || "Đã ẩn video khỏi pipeline.");
      await loadVideos();
      await loadSummary();
    } catch (error) {
      toast.error("Ẩn video thất bại.");
    }
  };

  const handleHardDelete = async () => {
    if (!requireSelection()) return;

    const confirmed = window.confirm(
      `XÓA VĨNH VIỄN ${selectedIds.length} video và dữ liệu liên quan? Sau đó nên build lại trend_history và prediction.`
    );

    if (!confirmed) return;

    try {
      const result = await hardDeleteAdminVideos(selectedIds);
      toast.success(result.message || "Đã xóa vĩnh viễn video.");
      await loadVideos();
      await loadSummary();
    } catch (error) {
      toast.error("Xóa vĩnh viễn thất bại.");
    }
  };

  const handleRunYoloPending = async () => {
    const pendingCount = Number(summary?.pending || 0);

    if (pendingCount <= 0) {
      toast.success("Không còn video pending cần xử lý YOLO.");
      return;
    }

    const confirmed = window.confirm(
      `Bắt đầu chạy YOLO cho ${formatNumber(pendingCount)} video đang chờ trong phạm vi `
    );

    if (!confirmed) return;

    try {
      setYoloTaskStarting(true);

      const result = await runProcessYolo({
        batch_size: 50,
        confidence: 0.35,
      });

      toast.success(result?.message || "Đã bắt đầu xử lý YOLO cho video đang chờ.");
      await loadSummary();
    } catch (error) {
      console.error("Run YOLO pending error:", error);
      toast.error("Không thể bắt đầu xử lý YOLO.");
    } finally {
      setYoloTaskStarting(false);
    }
  };

  const handleUpdateCovers = async () => {
    const selectedMode = selectedIds.length > 0;
    const limit = selectedMode ? selectedIds.length : 300;

    const confirmed = window.confirm(
      selectedMode
        ? `Cập nhật ảnh bìa cho ${selectedIds.length} video đã chọn?`
        : "Cập nhật ảnh bìa cho tối đa 300 video đang thiếu cover_url trong phạm vi đang lọc?"
    );

    if (!confirmed) return;

    try {
      const response = await startAdminVideoCoverUpdater({
        video_ids: selectedMode ? selectedIds : [],
        limit,
        concurrent_tabs: 2,
        headless: true,
        scope: filters.scope || "in_scope",
      });

      const task = response.task || response.data?.task || response;
      setCoverTask(task);
      toast.success("Đã bắt đầu cập nhật ảnh bìa.");
    } catch (error) {
      toast.error("Không thể bắt đầu cập nhật ảnh bìa.");
    }
  };

  const goPage = (nextPage) => {
    if (nextPage < 1 || nextPage > meta.total_pages) return;
    setPage(nextPage);
  };

  return (
    <div className="admin-page admin-video-page">
      <section className="admin-video-hero">
        <div className="admin-video-hero-top">
          <div>
            <span className="admin-video-eyebrow">Quản trị dữ liệu video</span>
            <h1>Quản lý video TikTok</h1>
            <p>
              Kiểm tra video đã crawl, trạng thái YOLO, ảnh bìa, hashtag, item thời trang
              và các thao tác làm sạch dữ liệu trước khi đưa vào pipeline xu hướng.
            </p>
          </div>

          <div className="admin-video-hero-actions">
            <button className="admin-video-hero-btn" onClick={loadVideos}>
              <RefreshCw size={17} />
              Làm mới
            </button>
        </div>
      </div>
        <div className="admin-video-summary-grid">
          <div className="admin-video-summary-card">
            <span>Video trong phạm vi</span>
            <strong>{formatNumber(summary?.total_in_scope)}</strong>
            <small>Dùng cho pipeline</small>
          </div>

          <div className="admin-video-summary-card">
            <span>YOLO hợp lệ</span>
            <strong>{formatNumber(summary?.success)}</strong>
            <small>Được đưa vào trend</small>
          </div>

          <div className="admin-video-summary-card">
            <span>Không thời trang</span>
            <strong>{formatNumber(summary?.failed_no_fashion)}</strong>
            <small>Lọc nhiễu dữ liệu</small>
          </div>

          <div className="admin-video-summary-card">
            <span>Lỗi khung hình</span>
            <strong>{formatNumber(summary?.failed_no_frame)}</strong>
            <small>Lỗi kỹ thuật tải video</small>
          </div>

          <div className="admin-video-summary-card">
            <span>Đang chờ</span>
            <strong>{formatNumber(summary?.pending)}</strong>
            <small>Chưa chạy YOLO</small>
          </div>

          <div className="admin-video-summary-card">
            <span>Tỉ lệ nhận diện</span>
            <strong>{Number(summary?.fashion_detection_rate || 0).toFixed(2)}%</strong>
            <small>success / nhóm đánh giá</small>
          </div>
        </div>
      </section>

      <section className="admin-video-toolbar">
        <div className="admin-video-toolbar-header">
          <div>
            <h2>Bộ lọc video</h2>
            <p>Giữ lại các bộ lọc cần thiết để trang gọn, dễ dùng và không bị rối.</p>
          </div>
        </div>

        <form onSubmit={handleApplyFilters}>
          <div className="admin-video-filter-grid">
            <div className="admin-video-field">
              <label>Tìm kiếm</label>
              <input
                value={draftFilters.search}
                onChange={(event) => handleFilterChange("search", event.target.value)}
                placeholder="Caption, TikTok ID, URL, hashtag, item..."
              />
            </div>

            <div className="admin-video-field">
              <label>Trạng thái</label>
              <select
                value={draftFilters.status}
                onChange={(event) => handleFilterChange("status", event.target.value)}
              >
                {STATUS_OPTIONS.map((option) => (
                  <option value={option.value} key={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="admin-video-field">
              <label>Phạm vi</label>
              <select
                value={draftFilters.scope}
                onChange={(event) => handleFilterChange("scope", event.target.value)}
              >
                {SCOPE_OPTIONS.map((option) => (
                  <option value={option.value} key={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="admin-video-field">
              <label>Hashtag</label>
              <input
                value={draftFilters.hashtag}
                onChange={(event) => handleFilterChange("hashtag", event.target.value)}
                placeholder="Ví dụ: outfit, y2k"
              />
            </div>

            <div className="admin-video-field">
              <label>Item YOLO</label>
              <select
                value={draftFilters.item}
                onChange={(event) => handleFilterChange("item", event.target.value)}
              >
                <option value="">Tất cả</option>
                {fashionOptions.map((item) => (
                  <option value={item} key={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>

            <div className="admin-video-field">
              <label>Sắp xếp</label>
              <select
                value={draftFilters.sort_by}
                onChange={(event) => handleFilterChange("sort_by", event.target.value)}
              >
                {SORT_OPTIONS.map((option) => (
                  <option value={option.value} key={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="admin-video-field">
              <label>Số dòng/trang</label>
              <select
                value={draftFilters.page_size}
                onChange={(event) =>
                  handleFilterChange("page_size", Number(event.target.value))
                }
              >
                {[25, 50, 100].map((size) => (
                  <option value={size} key={size}>
                    {size}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="admin-video-filter-actions">
            <button className="admin-video-button primary" type="submit">
              <Search size={17} />
              Áp dụng bộ lọc
            </button>

            <button className="admin-video-button gray" type="button" onClick={handleResetFilters}>
              <Filter size={17} />
              Đặt lại
            </button>
          </div>
        </form>
      </section>

      {coverTask && ["queued", "running"].includes(coverTask.status) && (
        <div className="admin-video-cover-task">
          <div>
            <strong>Đang cập nhật ảnh bìa</strong>
            <span>
              {formatNumber(coverTask.progress?.processed)} / {formatNumber(coverTask.progress?.total)} video
              · Thành công {formatNumber(coverTask.progress?.success)}
              · Thất bại {formatNumber(coverTask.progress?.failed)}
            </span>
          </div>
          <RefreshCw className="spin-icon" size={20} />
        </div>
      )}

      <section className="admin-video-list-card">
        <div className="admin-video-list-header">
          <div>
            <h2>Danh sách video</h2>
            <p>
              Đang hiển thị {formatNumber(videos.length)} / {formatNumber(meta.total)} video.
              Đã chọn {formatNumber(selectedCount)} video.
            </p>
          </div>
        </div>

        <div className="admin-video-bulk-actions">
          <div className="admin-video-bulk-actions-left">
            <button className="admin-video-button blue" disabled={selectedCount === 0} onClick={handleResetYolo}>
              <RotateCcw size={16} />
              Reset YOLO
            </button>

            <button
              className="admin-video-button orange"
              onClick={handleRunYoloPending}
              disabled={yoloTaskStarting || Number(summary?.pending || 0) <= 0}
              title="Chạy YOLO cho toàn bộ video pending trong phạm vi"
            >
              <Play size={16} />
              Khởi chạy YOLO
            </button>

            <button className="admin-video-button green" disabled={selectedCount === 0} onClick={handleMarkInScope}>
              <ShieldCheck size={16} />
              Đưa vào pipeline
            </button>

            <button className="admin-video-button blue" onClick={handleUpdateCovers}>
              <ImageIcon size={16} />
              Cập nhật ảnh bìa
            </button>
          </div>

          <div className="admin-video-bulk-actions-right">
            <button className="admin-video-button gray" disabled={selectedCount === 0} onClick={handleArchive}>
              <Archive size={16} />
              Ẩn khỏi pipeline
            </button>

            <button className="admin-video-button red" disabled={selectedCount === 0} onClick={handleHardDelete}>
              <Trash2 size={16} />
              Xóa vĩnh viễn
            </button>
          </div>
        </div>

        <div className="admin-video-table-wrap">
          <table className="admin-video-table">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    checked={allVisibleSelected}
                    onChange={toggleSelectAllVisible}
                  />
                </th>
                <th>Video</th>
                <th>Caption</th>
                <th>Hashtag</th>
                <th>Trạng thái</th>
                <th>Lượt xem</th>
                <th>Item</th>
                <th>Thao tác</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8}>
                    <div className="admin-video-empty-row">Đang tải danh sách video...</div>
                  </td>
                </tr>
              ) : videos.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <div className="admin-video-empty-row">Không tìm thấy video phù hợp.</div>
                  </td>
                </tr>
              ) : (
                videos.map((video) => (
                  <tr key={video.video_id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(video.video_id)}
                        onChange={() => toggleSelected(video.video_id)}
                      />
                    </td>

                    <td>
                      <div className="admin-video-cell">
                        <VideoCover video={video} />
                        <div>
                          <div className="admin-video-id">#{video.video_id}</div>
                          <span className="admin-video-tiktok-id">{video.tiktok_video_id}</span>
                        </div>
                      </div>
                    </td>

                    <td>
                      <div className="admin-video-caption">
                        {compactText(video.description)}
                      </div>
                    </td>

                    <td>
                      <ChipList items={video.hashtags} type="tag" limit={3} />
                    </td>

                    <td>
                      <span className={`admin-video-status ${statusClass(video.processing_status)}`}>
                        {video.processing_status_label || video.processing_status || "Không rõ"}
                      </span>
                    </td>

                    <td>
                      <span className="admin-video-views">{formatNumber(video.view_count)}</span>
                    </td>

                    <td>
                      <ChipList items={video.fashion_items} type="item" limit={2} />
                    </td>

                    <td>
                      <div className="admin-video-row-actions">
                        <button
                          className="admin-video-icon-btn"
                          title="Xem chi tiết"
                          onClick={() => handleViewDetail(video.video_id)}
                        >
                          <Eye size={17} />
                        </button>

                        {video.video_url && (
                          <a
                            className="admin-video-icon-btn"
                            href={video.video_url}
                            target="_blank"
                            rel="noreferrer"
                            title="Mở TikTok"
                          >
                            <ExternalLink size={17} />
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="admin-video-pagination">
          <button disabled={page <= 1} onClick={() => goPage(page - 1)}>
            <ChevronLeft size={16} />
          </button>
          <span>
            Trang {formatNumber(meta.page)} / {formatNumber(meta.total_pages)}
          </span>
          <button disabled={page >= meta.total_pages} onClick={() => goPage(page + 1)}>
            <ChevronRight size={16} />
          </button>
        </div>
      </section>

      {(selectedDetail || detailLoading) && (
        <>
          <div className="admin-video-drawer-backdrop" onClick={() => setSelectedDetail(null)} />
          <aside className="admin-video-drawer">
            {detailLoading ? (
              <div className="admin-video-empty-row">Đang tải chi tiết video...</div>
            ) : (
              <>
                <div className="admin-video-drawer-header">
                  <div>
                    <h3>Chi tiết video #{selectedDetail.video_id}</h3>
                    <p>{selectedDetail.tiktok_video_id}</p>
                  </div>
                  <button className="admin-video-icon-btn" onClick={() => setSelectedDetail(null)}>
                    <X size={18} />
                  </button>
                </div>

                {isValidImageUrl(selectedDetail.cover_url) ? (
                  <img className="admin-video-drawer-cover" src={selectedDetail.cover_url} alt="cover" />
                ) : (
                  <div className="admin-video-drawer-cover admin-video-drawer-cover-empty">
                    <ImageIcon size={28} />
                    <span>Video chưa có ảnh bìa hợp lệ</span>
                  </div>
                )}

                <div className="admin-video-drawer-section">
                  <h4>Thông tin chính</h4>
                  <p className="admin-video-drawer-caption">
                    {compactText(selectedDetail.description)}
                  </p>

                  <div className="admin-video-detail-grid">
                    <div className="admin-video-detail-item">
                      <span>Trạng thái</span>
                      <strong>{selectedDetail.processing_status_label}</strong>
                    </div>
                    <div className="admin-video-detail-item">
                      <span>Phạm vi</span>
                      <strong>{selectedDetail.is_in_scope ? "Trong phạm vi" : "Ngoài phạm vi"}</strong>
                    </div>
                    <div className="admin-video-detail-item">
                      <span>Ngày đăng</span>
                      <strong>{formatDate(selectedDetail.published_at)}</strong>
                    </div>
                    <div className="admin-video-detail-item">
                      <span>Độ tin cậy ngày</span>
                      <strong>{selectedDetail.date_confidence || "unknown"}</strong>
                    </div>
                  </div>
                </div>

                <div className="admin-video-drawer-section">
                  <h4>Chỉ số mới nhất</h4>
                  <div className="admin-video-detail-grid">
                    <div className="admin-video-detail-item">
                      <span>Lượt xem</span>
                      <strong>{formatNumber(selectedDetail.view_count)}</strong>
                    </div>
                    <div className="admin-video-detail-item">
                      <span>Lượt thích</span>
                      <strong>{formatNumber(selectedDetail.like_count)}</strong>
                    </div>
                    <div className="admin-video-detail-item">
                      <span>Bình luận</span>
                      <strong>{formatNumber(selectedDetail.comment_count)}</strong>
                    </div>
                    <div className="admin-video-detail-item">
                      <span>Chia sẻ</span>
                      <strong>{formatNumber(selectedDetail.share_count)}</strong>
                    </div>
                  </div>
                </div>

                <div className="admin-video-drawer-section">
                  <h4>Hashtag</h4>
                  <ChipList items={selectedDetail.hashtags} type="tag" limit={20} />
                </div>

                <div className="admin-video-drawer-section">
                  <h4>Item YOLO</h4>
                  <ChipList items={selectedDetail.fashion_items} type="item" limit={20} />
                </div>

                {selectedDetail.latest_ai_analysis && (
                  <div className="admin-video-drawer-section">
                    <h4>AI analysis mới nhất</h4>
                    <div className="admin-video-detail-grid">
                      <div className="admin-video-detail-item">
                        <span>Confidence</span>
                        <strong>
                          {Number(selectedDetail.latest_ai_analysis.confidence_score || 0).toFixed(4)}
                        </strong>
                      </div>
                      <div className="admin-video-detail-item">
                        <span>Loại phân tích</span>
                        <strong>{selectedDetail.latest_ai_analysis.analysis_type}</strong>
                      </div>
                    </div>
                  </div>
                )}

                <div className="admin-video-drawer-actions">
                  {selectedDetail.video_url && (
                    <a
                      className="admin-video-button blue"
                      href={selectedDetail.video_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <ExternalLink size={16} />
                      Mở TikTok
                    </a>
                  )}
                  <button
                    className="admin-video-button primary"
                    onClick={() => {
                      setSelectedIds([selectedDetail.video_id]);
                      handleUpdateCovers();
                    }}
                  >
                    <ImageIcon size={16} />
                    Cập nhật ảnh bìa
                  </button>
                </div>
              </>
            )}
          </aside>
        </>
      )}
    </div>
  );
}

export default AdminVideoManagement;
