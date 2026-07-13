import React, { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import {
  Search,
  Plus,
  Edit3,
  Lock,
  Unlock,
  ShieldCheck,
  UserCog,
  X,
  MailCheck,
  MailWarning,
} from "lucide-react";

import {
  getAdvancedUsers,
  createAdminUser,
  updateAdminUser,
  updateAdminUserStatus,
} from "../../controllers/admin/adminController";

import UserAvatar from "../../components/UserAvatar";
import SkeletonCard from "../../components/SkeletonCard";

const DEFAULT_FORM = {
  username: "",
  email: "",
  password: "",
  full_name: "",
  avatar_url: "",
  role_name: "user",
  is_active: true,
  is_email_verified: true,
};

function formatDate(value) {
  if (!value) return "Chưa có";
  return new Date(value).toLocaleString("vi-VN");
}

function normalizeResponse(response) {
  return response?.data || response || [];
}

function StatusBadge({ active }) {
  return active ? (
    <span className="admin-user-badge active">Đang hoạt động</span>
  ) : (
    <span className="admin-user-badge locked">Đã khóa</span>
  );
}

function RoleBadge({ role }) {
  const normalized = String(role || "user").toLowerCase();

  const label = normalized === "admin" ? "Quản trị viên" : "Người dùng";

  return (
    <span
      className={
        normalized === "admin"
          ? "admin-user-badge admin"
          : "admin-user-badge user"
      }
    >
      {label}
    </span>
  );
}

function VerifiedBadge({ verified }) {
  return verified ? (
    <span className="admin-user-badge verified">
      <MailCheck size={14} />
      Đã xác thực
    </span>
  ) : (
    <span className="admin-user-badge unverified">
      <MailWarning size={14} />
      Chưa xác thực
    </span>
  );
}

function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  const [filters, setFilters] = useState({
    search: "",
    role: "all",
    active: "all",
    verified: "all",
  });

  const [modalOpen, setModalOpen] = useState(false);
  const [mode, setMode] = useState("create");
  const [selectedUser, setSelectedUser] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async (customFilters = filters) => {
    try {
      setLoading(true);

      const response = await getAdvancedUsers({
        search: customFilters.search,
        role: customFilters.role,
        active: customFilters.active,
        verified: customFilters.verified,
        limit: 200,
      });

      setUsers(normalizeResponse(response));
    } catch (error) {
      console.error("Load admin users error:", error);
      toast.error("Không thể tải danh sách người dùng");
    } finally {
      setLoading(false);
    }
  };

  const stats = useMemo(() => {
    const total = users.length;
    const admins = users.filter((u) => u.role === "admin").length;
    const active = users.filter((u) => u.is_active).length;
    const locked = users.filter((u) => !u.is_active).length;
    const verified = users.filter((u) => u.is_email_verified).length;

    return { total, admins, active, locked, verified };
  }, [users]);

  const handleFilterChange = (event) => {
    const newFilters = {
      ...filters,
      [event.target.name]: event.target.value,
    };

    setFilters(newFilters);
  };

  const currentUser = JSON.parse(localStorage.getItem("user") || "{}");

  const isSuperAdmin = currentUser?.username === "admin123";

  const isTargetSuperAdmin = (user) => user?.username === "admin123";
  const isTargetAdmin = (user) => user?.role === "admin";

  const canEditUser = (user) => {
    if (isTargetSuperAdmin(user)) return false;

    if (isSuperAdmin) return true;

    if (isTargetAdmin(user)) return false;

    return true;
  };

  const canToggleUser = (user) => {
    if (isTargetSuperAdmin(user)) return false;

    if (currentUser?.user_id === user?.user_id) return false;

    if (isSuperAdmin) return true;

    if (isTargetAdmin(user)) return false;

    return true;
  };

  const handleSearchSubmit = (event) => {
    event.preventDefault();
    loadUsers(filters);
  };

  const handleApplyFilters = () => {
    loadUsers(filters);
  };

  const handleResetFilters = () => {
    const reset = {
      search: "",
      role: "all",
      active: "all",
      verified: "all",
    };

    setFilters(reset);
    loadUsers(reset);
  };

  const openCreateModal = () => {
    setMode("create");
    setSelectedUser(null);
    setForm(DEFAULT_FORM);
    setModalOpen(true);
  };

  const openEditModal = (user) => {
    setMode("edit");
    setSelectedUser(user);

    setForm({
      username: user.username || "",
      email: user.email || "",
      password: "",
      full_name: user.full_name || "",
      avatar_url: user.avatar_url || "",
      role_name: user.role || "user",
      is_active: Boolean(user.is_active),
      is_email_verified: Boolean(user.is_email_verified),
    });

    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setMode("create");
    setSelectedUser(null);
    setForm(DEFAULT_FORM);
  };

  const handleFormChange = (event) => {
    const { name, value, type, checked } = event.target;

    setForm({
      ...form,
      [name]: type === "checkbox" ? checked : value,
    });
  };

  const validateForm = () => {
    if (!form.username.trim()) {
      toast.error("Username không được để trống");
      return false;
    }

    if (!form.email.trim()) {
      toast.error("Email không được để trống");
      return false;
    }

    if (!form.email.includes("@")) {
      toast.error("Email không đúng định dạng");
      return false;
    }

    if (mode === "create" && !form.password.trim()) {
      toast.error("Mật khẩu không được để trống");
      return false;
    }

    if (mode === "create" && form.password.length < 6) {
      toast.error("Mật khẩu nên có ít nhất 6 ký tự");
      return false;
    }

    return true;
  };

  const handleSaveUser = async (event) => {
    event.preventDefault();

    if (!validateForm()) return;

    try {
      setSaving(true);

      if (mode === "create") {
        const payload = {
          username: form.username.trim(),
          email: form.email.trim(),
          password: form.password,
          full_name: form.full_name.trim() || null,
          role_name: form.role_name,
          is_active: form.is_active,
          is_email_verified: form.is_email_verified,
        };

        await createAdminUser(payload);
        toast.success("Tạo tài khoản thành công");
      } else {
        const payload = {
          username: form.username.trim(),
          email: form.email.trim(),
          full_name: form.full_name.trim() || null,
          avatar_url: form.avatar_url.trim() || null,
          role_name: form.role_name,
          is_active: form.is_active,
          is_email_verified: form.is_email_verified,
        };

        await updateAdminUser(selectedUser.user_id, payload);
        toast.success("Cập nhật tài khoản thành công");
      }

      closeModal();
      loadUsers(filters);
    } catch (error) {
      console.error("Save user error:", error);
      toast.error(error.response?.data?.detail || "Không thể lưu tài khoản");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleStatus = async (user) => {
    const nextStatus = !user.is_active;

    const confirmMessage = nextStatus
      ? `Bạn muốn mở khóa tài khoản "${user.username}"?`
      : `Bạn muốn khóa tài khoản "${user.username}"?`;

    const ok = window.confirm(confirmMessage);

    if (!ok) return;

    try {
      await updateAdminUserStatus(user.user_id, nextStatus);

      toast.success(nextStatus ? "Đã mở khóa tài khoản" : "Đã khóa tài khoản");

      loadUsers(filters);
    } catch (error) {
      console.error("Toggle user status error:", error);
      toast.error(error.response?.data?.detail || "Không thể cập nhật trạng thái");
    }
  };

  return (
    <div className="admin-page admin-users-page">
      <div className="admin-users-hero">
        <div>
          <span>User Management Pro</span>
          <h1>Quản lý tài khoản người dùng</h1>
          <p>
            Thêm tài khoản, chỉnh sửa thông tin, cấp quyền admin/user và khóa hoặc
            mở khóa người dùng trong hệ thống.
          </p>
        </div>

        <button className="btn-primary-pink admin-add-user-btn" onClick={openCreateModal}>
          <Plus size={18} />
          Thêm user
        </button>
      </div>

      <div className="admin-users-stat-grid">
        <div>
          <span>Tổng user</span>
          <strong>{stats.total}</strong>
        </div>
        <div>
          <span>Admin</span>
          <strong>{stats.admins}</strong>
        </div>
        <div>
          <span>Đã kích hoạt</span>
          <strong>{stats.active}</strong>
        </div>
        <div>
          <span>Đã khóa</span>
          <strong>{stats.locked}</strong>
        </div>
        <div>
          <span>Đã xác thực Email</span>
          <strong>{stats.verified}</strong>
        </div>
      </div>

      <div className="admin-user-filter-card">
        <form className="admin-user-filter-bar" onSubmit={handleSearchSubmit}>
          <div className="admin-user-search">
            <Search size={18} />
            <input
              name="search"
              value={filters.search}
              onChange={handleFilterChange}
              placeholder="Tìm username, email, họ tên..."
            />
          </div>

          <select name="role" value={filters.role} onChange={handleFilterChange}>
            <option value="all">Vai trò: Tất cả</option>
            <option value="admin" disabled={!isSuperAdmin}>Quản trị viên</option>
            <option value="user">Người dùng</option>
          </select>

          <select name="active" value={filters.active} onChange={handleFilterChange}>
            <option value="all">Trạng thái: Tất cả</option>
            <option value="active">Đang hoạt động</option>
            <option value="locked">Đã khóa</option>
          </select>

          <select
            name="verified"
            value={filters.verified}
            onChange={handleFilterChange}
          >
            <option value="all">Email: Tất cả</option>
            <option value="verified">Đã xác thực</option>
            <option value="unverified">Chưa xác thực</option>
          </select>

          <button type="submit" className="admin-filter-btn">
            Tìm kiếm
          </button>

          <button type="button" className="admin-reset-btn" onClick={handleResetFilters}>
            Làm mới
          </button>
        </form>

        <div className="admin-filter-helper">
          <ShieldCheck size={17} />
          <span>
            Admin có thể cấp quyền, khóa hoặc mở khóa user. User bị khóa sẽ không
            đăng nhập được.
          </span>
        </div>
      </div>

      <div className="card-box admin-users-table-card">
        <div className="section-header">
          <h5>Danh sách tài khoản</h5>
          <span>{users.length} users</span>
        </div>

        {loading ? (
          <SkeletonCard rows={7} />
        ) : (
          <div className="table-responsive admin-users-table-wrap">
            <table className="table align-middle admin-users-table">
              <thead>
                <tr>
                  <th>Người dùng</th>
                  <th>Email</th>
                  <th>Vai trò</th>
                  <th>Xác thực email</th>
                  <th>Trạng thái</th>
                  <th>Lần đăng nhập cuối</th>
                  <th>Thao tác</th>
                </tr>
              </thead>

              <tbody>
                {users.length === 0 ? (
                  <tr>
                    <td colSpan="7">
                      <div className="admin-empty-row">
                        Không tìm thấy user phù hợp với bộ lọc.
                      </div>
                    </td>
                  </tr>
                ) : (
                  users.map((user) => (
                    <tr key={user.user_id}>
                      <td>
                        <div className="admin-user-cell">
                          <UserAvatar user={user} size={46} />

                          <div>
                            <strong>{user.username}</strong>
                            <span>{user.full_name || "Chưa cập nhật họ tên"}</span>
                          </div>
                        </div>
                      </td>

                      <td>
                        <div className="admin-user-email">{user.email}</div>
                      </td>

                      <td>
                        <RoleBadge role={user.role} />
                      </td>

                      <td>
                        <VerifiedBadge verified={user.is_email_verified} />
                      </td>

                      <td>
                        <StatusBadge active={user.is_active} />
                      </td>

                      <td>{formatDate(user.last_login)}</td>

                      <td>
                        <div className="admin-user-actions">
                          <button
                            className="admin-action-btn edit"
                            onClick={() => openEditModal(user)}
                            disabled={!canEditUser(user)}
                            title={
                              canEditUser(user)
                                ? "Sửa user / cấp quyền"
                                : "Bạn không có quyền chỉnh sửa tài khoản này"
                            }
                          >
                            <Edit3 size={16} />
                          </button>

                          <button
                            className={
                              user.is_active
                                ? "admin-action-btn lock"
                                : "admin-action-btn unlock"
                            }
                            onClick={() => handleToggleStatus(user)}
                            disabled={!canToggleUser(user)}
                            title={
                              canToggleUser(user)
                                ? user.is_active
                                  ? "Khóa tài khoản"
                                  : "Mở khóa tài khoản"
                                : "Bạn không có quyền khóa/mở khóa tài khoản này"
                            }
                          >
                            {user.is_active ? <Lock size={16} /> : <Unlock size={16} />}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {modalOpen && (
        <div className="admin-user-modal-backdrop">
          <div className="admin-user-modal">
            <div className="admin-user-modal-header">
              <div>
                <span>{mode === "create" ? "Tạo tài khoản" : "Chỉnh sửa tài khoản"}</span>
                <h3>{mode === "create" ? "Thêm tài khoản mới" : "Sửa tài khoản"}</h3>
              </div>

              <button onClick={closeModal}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSaveUser}>
              <div className="admin-user-form-grid">
                <div className="form-group-pro">
                  <label>Username</label>
                  <input
                    name="username"
                    value={form.username}
                    onChange={handleFormChange}
                    placeholder="username"
                  />
                </div>

                <div className="form-group-pro">
                  <label>Email</label>
                  <input
                    name="email"
                    type="email"
                    value={form.email}
                    onChange={handleFormChange}
                    placeholder="user@gmail.com"
                  />
                </div>

                {mode === "create" && (
                  <div className="form-group-pro">
                    <label>Mật khẩu</label>
                    <input
                      name="password"
                      type="password"
                      value={form.password}
                      onChange={handleFormChange}
                      placeholder="Mật khẩu đăng nhập"
                    />
                  </div>
                )}

                <div className="form-group-pro">
                  <label>Họ tên</label>
                  <input
                    name="full_name"
                    value={form.full_name}
                    onChange={handleFormChange}
                    placeholder="Họ tên người dùng"
                  />
                </div>

                {mode === "edit" && (
                  <div className="form-group-pro admin-user-form-full">
                    <label>Avatar URL</label>
                    <input
                      name="avatar_url"
                      value={form.avatar_url}
                      onChange={handleFormChange}
                      placeholder="https://..."
                    />
                  </div>
                )}

                <div className="form-group-pro">
                  <label>Role / Cấp quyền</label>
                  <select
                    name="role_name"
                    value={form.role_name}
                    onChange={handleFormChange}
                  >
                    <option value="user">User</option>
                    <option value="admin" disabled={!isSuperAdmin}>
                      Admin
                    </option>
                  </select>
                </div>

                <div className="admin-user-toggle-box">
                  <label>
                    <input
                      type="checkbox"
                      name="is_active"
                      checked={form.is_active}
                      onChange={handleFormChange}
                    />
                    <span>Tài khoản hoạt động</span>
                  </label>

                  <label>
                    <input
                      type="checkbox"
                      name="is_email_verified"
                      checked={form.is_email_verified}
                      onChange={handleFormChange}
                    />
                    <span>Email đã xác thực</span>
                  </label>
                </div>
              </div>

              <div className="admin-user-modal-footer">
                <button type="button" className="admin-cancel-btn" onClick={closeModal}>
                  Hủy
                </button>

                <button className="btn-primary-pink" disabled={saving}>
                  {saving
                    ? "Đang lưu..."
                    : mode === "create"
                    ? "Tạo tài khoản"
                    : "Lưu thay đổi"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default AdminUsers;