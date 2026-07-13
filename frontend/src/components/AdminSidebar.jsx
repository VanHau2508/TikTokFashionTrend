import React from "react";
import { NavLink } from "react-router-dom";
import {
  Shield,
  Users,
  Database,
  Settings,
  LogOut,
  LayoutDashboard,
  Video,
} from "lucide-react";

import { logout, getLocalUser } from "../controllers/authController";

function AdminSidebar() {
  const user = getLocalUser();

  return (
    <aside className="sidebar admin-sidebar">
      <div className="sidebar-brand">
        <div className="brand-icon admin-brand-icon">
          <Shield size={24} />
        </div>
        <div>
          <h3>Admin Panel</h3>
          <span>Quản trị hệ thống</span>
        </div>
      </div>

      <div className="sidebar-user admin-user-box">
        <div className="avatar-circle">
          {user?.username?.charAt(0)?.toUpperCase() || "A"}
        </div>
        <div>
          <strong>{user?.username || "Admin"}</strong>
          <span>Quản trị viên</span>
        </div>
      </div>

      <div className="sidebar-group-title">QUẢN TRỊ</div>

      <nav className="sidebar-nav">
        <NavLink
          to="/admin/dashboard"
          className={({ isActive }) =>
            isActive ? "sidebar-link active" : "sidebar-link"
          }
        >
          <LayoutDashboard size={20} />
          <span>Tổng quan admin</span>
        </NavLink>

        <NavLink
          to="/admin/users"
          className={({ isActive }) =>
            isActive ? "sidebar-link active" : "sidebar-link"
          }
        >
          <Users size={20} />
          <span>Người dùng</span>
        </NavLink>

        <NavLink
          to="/admin/videos"
          className={({ isActive }) =>
            isActive ? "sidebar-link active" : "sidebar-link"
          }
        >
          <Video size={20} />
          <span>Quản lý video</span>
        </NavLink>

        <NavLink
          to="/admin/jobs"
          className={({ isActive }) =>
            isActive ? "sidebar-link active" : "sidebar-link"
          }
        >
          <Database size={20} />
          <span>Lịch sử crawl</span>
        </NavLink>

        <NavLink
          to="/admin/tasks"
          className={({ isActive }) =>
            isActive ? "sidebar-link active" : "sidebar-link"
          }
        >
          <Settings size={20} />
          <span>Tác vụ hệ thống</span>
        </NavLink>
      </nav>

      <button className="sidebar-logout" onClick={logout}>
        <LogOut size={18} />
        <span>Đăng xuất</span>
      </button>
    </aside>
  );
}

export default AdminSidebar;
