import React, { useEffect, useState } from "react";
import {
  Users,
  Video,
  Hash,
  Shirt,
  Bot,
  Database,
  Mail,
  Activity,
  ShieldCheck,
  AlertTriangle,
} from "lucide-react";
import toast from "react-hot-toast";

import StatCard from "../../components/StatCard";
import SkeletonCard from "../../components/SkeletonCard";
import { getAdminControlCenter } from "../../controllers/admin/adminController";

function formatNumber(value) {
  return Number(value || 0).toLocaleString("vi-VN");
}

function formatDate(value) {
  if (!value) return "Chưa có";
  return new Date(value).toLocaleString("vi-VN");
}

function getHealthStatusLabel(status) {
  const map = {
    connected: "Đã kết nối",
    ready: "Sẵn sàng",
    enabled: "Đã bật",
    not_configured: "Chưa cấu hình",
    missing_model: "Thiếu model",
    error: "Lỗi",
  };

  return map[status] || status || "Không rõ";
}

function HealthPill({ label, status, icon: Icon }) {
  const okStatuses = ["connected", "ready", "enabled"];
  const isOk = okStatuses.includes(status);

  return (
    <div className={isOk ? "admin-health-pill ok" : "admin-health-pill warning"}>
      <Icon size={20} />
      <div>
        <span>{label}</span>
        <strong>{getHealthStatusLabel(status)}</strong>
      </div>
    </div>
  );
}

function AdminDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      setLoading(true);
      const response = await getAdminControlCenter();
      const result = response?.data || response;
      setData(result);
    } catch (error) {
      toast.error("Không thể tải Admin Control Center");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div>
        <div className="skeleton-page-header" />
        <div className="row g-3">
          <div className="col-md-3"><SkeletonCard /></div>
          <div className="col-md-3"><SkeletonCard /></div>
          <div className="col-md-3"><SkeletonCard /></div>
          <div className="col-md-3"><SkeletonCard /></div>
        </div>
      </div>
    );
  }

  const summary = data?.summary || {};
  const latest = data?.latest || {};
  const health = data?.health || {};

  return (
    <div className="admin-page admin-dashboard-page">
      <div className="admin-control-hero">
        <div>
          <span>Admin Control Center</span>
          <h1>Trung tâm quản trị hệ thống</h1>
          <p>
            Theo dõi người dùng, dữ liệu TikTok, trạng thái AI model và crawler jobs.
          </p>
        </div>

        <button className="btn-primary-pink" onClick={loadDashboard}>
          Refresh
        </button>
      </div>

      <div className="row g-3 mb-4">
        <div className="col-md-3">
          <StatCard
            title="Người dùng"
            value={formatNumber(summary.total_users)}
            icon={Users}
            description={`${formatNumber(summary.verified_users)} đã xác thực email`}
            accent="pink"
          />
        </div>

        <div className="col-md-3">
          <StatCard
            title="Videos"
            value={formatNumber(summary.total_videos)}
            icon={Video}
            description={`${formatNumber(summary.yolo_success)} YOLO success`}
            accent="cyan"
          />
        </div>

        <div className="col-md-3">
          <StatCard
            title="Hashtags"
            value={formatNumber(summary.total_hashtags)}
            icon={Hash}
            description="Nguồn phân tích xu hướng"
            accent="navy"
          />
        </div>

        <div className="col-md-3">
          <StatCard
            title="Dự đoán LSTM"
            value={formatNumber(summary.total_predictions)}
            icon={Bot}
            description="Kết quả dự đoán LSTM"
            accent="pink"
          />
        </div>
      </div>

      <div className="row g-3 mb-4">
        <div className="col-lg-7">
          <div className="card-box h-100">
            <div className="section-header">
              <h5>System Health</h5>
              <span>Trạng thái hệ thống</span>
            </div>

            <div className="admin-health-grid">
              <HealthPill label="Database" status={health.database} icon={Database} />
              <HealthPill label="Crawler" status={health.crawler} icon={Activity} />
              <HealthPill label="YOLOv8" status={health.yolo} icon={Shirt} />
              <HealthPill label="LSTM" status={health.lstm} icon={Bot} />
              <HealthPill label="SMTP Gmail" status={health.smtp} icon={Mail} />
            </div>
          </div>
        </div>

        <div className="col-lg-5">
          <div className="card-box h-100">
            <div className="section-header">
              <h5>Latest Activity</h5>
              <span>Hoạt động gần nhất</span>
            </div>

            <div className="admin-latest-list">
              <div>
                <span>Video stats sync</span>
                <strong>{formatDate(latest.latest_video_stat_at)}</strong>
              </div>

              <div>
                <span>LSTM prediction</span>
                <strong>{formatDate(latest.latest_prediction_at)}</strong>
              </div>

              <div>
                <span>Latest crawler job</span>
                <strong>
                  {latest.latest_job_name || "Chưa có"} · {latest.latest_job_status || "N/A"}
                </strong>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="admin-warning-panel">
        <ShieldCheck size={28} />
        <div>
          <h5>Admin Notes</h5>
          <p>
            Trang quản trị này dùng để kiểm tra health, giám sát dữ liệu, chạy tác vụ và
            quản lý user. Với đồ án, đây là phần giúp hệ thống giống một sản phẩm thật hơn.
          </p>
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;