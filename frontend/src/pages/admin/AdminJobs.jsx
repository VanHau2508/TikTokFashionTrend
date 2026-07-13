import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  RefreshCcw,
  Search,
  XCircle,
} from "lucide-react";

import { getCrawlerJobs } from "../../controllers/admin/adminController";

function formatDate(value) {
  if (!value) return "Chưa có";

  try {
    return new Date(value).toLocaleString("vi-VN");
  } catch {
    return value;
  }
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("vi-VN");
}

function normalizeResponse(response) {
  return response?.data || response || [];
}

function getJobStatusMeta(status) {
  const normalized = String(status || "unknown").toLowerCase();

  if (normalized === "completed" || normalized === "success") {
    return {
      label: "Hoàn tất",
      className: "completed",
      icon: CheckCircle2,
    };
  }

  if (normalized === "running" || normalized === "pending" || normalized === "queued") {
    return {
      label: normalized === "pending" ? "Đang chờ" : "Đang chạy",
      className: "running",
      icon: Clock3,
    };
  }

  if (normalized === "failed" || normalized === "error") {
    return {
      label: "Thất bại",
      className: "failed",
      icon: XCircle,
    };
  }

  return {
    label: status || "Không rõ",
    className: "unknown",
    icon: AlertTriangle,
  };
}

function AdminJobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    loadJobs();
  }, []);

  const loadJobs = async () => {
    try {
      setLoading(true);
      const response = await getCrawlerJobs();
      setJobs(normalizeResponse(response));
    } catch (error) {
      console.error("Jobs error:", error);
    } finally {
      setLoading(false);
    }
  };

  const stats = useMemo(() => {
    const total = jobs.length;
    const completed = jobs.filter((job) => job.status === "completed").length;
    const failed = jobs.filter((job) => job.status === "failed").length;
    const videos = jobs.reduce(
      (sum, job) => sum + Number(job.videos_collected || 0),
      0
    );

    return { total, completed, failed, videos };
  }, [jobs]);

  const filteredJobs = useMemo(() => {
    const keyword = search.trim().toLowerCase();

    if (!keyword) return jobs;

    return jobs.filter((job) => {
      return [
        job.job_name,
        job.job_type,
        job.status,
        job.error_message,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(keyword));
    });
  }, [jobs, search]);

  if (loading) {
    return (
      <div className="admin-page admin-jobs-page">
        <div className="loading-box">Đang tải crawler jobs...</div>
      </div>
    );
  }

  return (
    <div className="admin-page admin-jobs-page">
      <div className="admin-jobs-hero">
        <div>
          <span>Giám sát crawler</span>
          <h1>Lịch sử crawl dữ liệu</h1>
          <p>
            Theo dõi lịch sử thu thập dữ liệu TikTok, số lượng video đã lấy và trạng thái xử lý job.
          </p>
        </div>

        <button className="admin-refresh-btn" onClick={loadJobs}>
          <RefreshCcw size={16} />
          Làm mới
        </button>
      </div>

      <div className="admin-jobs-stat-grid">
        <div>
          <span>Tổng công việc</span>
          <strong>{formatNumber(stats.total)}</strong>
        </div>
        <div>
          <span>Hoàn tất</span>
          <strong>{formatNumber(stats.completed)}</strong>
        </div>
        <div>
          <span>Thất bại</span>
          <strong>{formatNumber(stats.failed)}</strong>
        </div>
        <div>
          <span>Video đã thu thập</span>
          <strong>{formatNumber(stats.videos)}</strong>
        </div>
      </div>

      <div className="admin-jobs-filter-card">
        <div className="admin-jobs-search">
          <Search size={18} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Tìm theo tên job, loại, trạng thái hoặc lỗi..."
          />
        </div>
      </div>

      <div className="card-box admin-jobs-table-card">
        <div className="section-header">
          <div>
            <h5>Lịch sử crawler</h5>
            <span>{filteredJobs.length} / {jobs.length} jobs gần nhất</span>
          </div>
        </div>

        {filteredJobs.length === 0 ? (
          <div className="admin-empty-log">
            Không có crawler job phù hợp.
          </div>
        ) : (
          <div className="table-responsive admin-jobs-table-wrap">
            <table className="table align-middle admin-jobs-table">
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Loại</th>
                  <th>Trạng thái</th>
                  <th>Video</th>
                  <th>Ngày tạo</th>
                </tr>
              </thead>

              <tbody>
                {filteredJobs.map((job) => {
                  const statusMeta = getJobStatusMeta(job.status);
                  const StatusIcon = statusMeta.icon;

                  return (
                    <tr key={job.job_id}>
                      <td>
                        <div className="admin-job-name">
                          <strong>{job.job_name || "Crawler job"}</strong>
                          {job.error_message && (
                            <small>{job.error_message}</small>
                          )}
                        </div>
                      </td>

                      <td>
                        <span className="admin-job-type">{job.job_type || "N/A"}</span>
                      </td>

                      <td>
                        <span className={`admin-job-status ${statusMeta.className}`}>
                          <StatusIcon size={14} />
                          {statusMeta.label}
                        </span>
                      </td>

                      <td>
                        <strong>{formatNumber(job.videos_collected)}</strong>
                      </td>

                      <td>{formatDate(job.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default AdminJobs;
