import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { User, ShieldCheck, KeyRound, Mail } from "lucide-react";
import {
  getMyAccount,
  updateProfile,
  changePassword,
} from "../controllers/accountController";

function formatDate(value) {
  if (!value) return "Chưa có";
  return new Date(value).toLocaleString("vi-VN");
}

function Account() {
  const [account, setAccount] = useState(null);
  const [profileForm, setProfileForm] = useState({
    full_name: "",
    avatar_url: "",
  });

  const [passwordForm, setPasswordForm] = useState({
    current_password: "",
    new_password: "",
    confirm_password: "",
  });

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAccount();
  }, []);

  const loadAccount = async () => {
    try {
      setLoading(true);

      const data = await getMyAccount();

      setAccount(data);
      setProfileForm({
        full_name: data.full_name || "",
        avatar_url: data.avatar_url || "",
      });
    } catch (error) {
      toast.error("Không thể tải thông tin tài khoản");
    } finally {
      setLoading(false);
    }
  };

  const handleProfileChange = (event) => {
    setProfileForm({
      ...profileForm,
      [event.target.name]: event.target.value,
    });
  };

  const handlePasswordChange = (event) => {
    setPasswordForm({
      ...passwordForm,
      [event.target.name]: event.target.value,
    });
  };

  const handleUpdateProfile = async (event) => {
    event.preventDefault();

    try {
      const response = await updateProfile(profileForm);

      setAccount(response.user);
        localStorage.setItem("user", JSON.stringify(response.user));
        window.dispatchEvent(new Event("account-updated"));

      toast.success(response.message || "Cập nhật hồ sơ thành công");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Cập nhật hồ sơ thất bại");
    }
  };

  const handleChangePassword = async (event) => {
    event.preventDefault();

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      toast.error("Mật khẩu xác nhận không khớp");
      return;
    }

    try {
      const response = await changePassword(
        passwordForm.current_password,
        passwordForm.new_password
      );

      toast.success(response.message || "Đổi mật khẩu thành công");

      setPasswordForm({
        current_password: "",
        new_password: "",
        confirm_password: "",
      });
    } catch (error) {
      toast.error(error.response?.data?.detail || "Đổi mật khẩu thất bại");
    }
  };

  if (loading) {
    return <div className="loading-box">Đang tải tài khoản...</div>;
  }

  return (
    <div>
      <h1 className="page-title">Tài khoản của tôi</h1>
      <p className="page-subtitle">
        Quản lý hồ sơ cá nhân, trạng thái email và bảo mật tài khoản.
      </p>

      <div className="account-hero-card">
        <div className="account-avatar">
          {account?.avatar_url ? (
            <img src={account.avatar_url} alt={account.username} />
          ) : (
            <span>{account?.username?.charAt(0)?.toUpperCase()}</span>
          )}
        </div>

        <div>
          <h2>{account?.full_name || account?.username}</h2>
          <p>@{account?.username}</p>

          <div className="account-badge-row">
            <span>{account?.role}</span>
            <span className={account?.is_email_verified ? "verified" : "warning"}>
              {account?.is_email_verified ? "Email đã xác thực" : "Email chưa xác thực"}
            </span>
          </div>
        </div>
      </div>

      <div className="row g-3 mb-4">
        <div className="col-lg-4">
          <div className="account-info-card">
            <User size={24} />
            <span>Username</span>
            <strong>{account?.username}</strong>
          </div>
        </div>

        <div className="col-lg-4">
          <div className="account-info-card">
            <Mail size={24} />
            <span>Email</span>
            <strong>{account?.email}</strong>
          </div>
        </div>

        <div className="col-lg-4">
          <div className="account-info-card">
            <ShieldCheck size={24} />
            <span>Lần đăng nhập gần nhất</span>
            <strong>{formatDate(account?.last_login)}</strong>
          </div>
        </div>
      </div>

      <div className="row g-3">
        <div className="col-lg-6">
          <div className="card-box">
            <div className="section-header">
              <h5>Cập nhật hồ sơ</h5>
              <span>Profile settings</span>
            </div>

            <form onSubmit={handleUpdateProfile}>
              <div className="form-group-pro">
                <label>Họ tên</label>
                <input
                  name="full_name"
                  value={profileForm.full_name}
                  onChange={handleProfileChange}
                  placeholder="Nhập họ tên"
                />
              </div>

              <div className="form-group-pro">
                <label>Avatar URL</label>
                <input
                  name="avatar_url"
                  value={profileForm.avatar_url}
                  onChange={handleProfileChange}
                  placeholder="https://..."
                />
              </div>

              <button className="btn-primary-pink">
                Lưu thay đổi
              </button>
            </form>
          </div>
        </div>

        <div className="col-lg-6">
          <div className="card-box">
            <div className="section-header">
              <h5>Đổi mật khẩu</h5>
              <span>Security</span>
            </div>

            <form onSubmit={handleChangePassword}>
              <div className="form-group-pro">
                <label>Mật khẩu hiện tại</label>
                <input
                  type="password"
                  name="current_password"
                  value={passwordForm.current_password}
                  onChange={handlePasswordChange}
                  placeholder="Nhập mật khẩu hiện tại"
                />
              </div>

              <div className="form-group-pro">
                <label>Mật khẩu mới</label>
                <input
                  type="password"
                  name="new_password"
                  value={passwordForm.new_password}
                  onChange={handlePasswordChange}
                  placeholder="Nhập mật khẩu mới"
                />
              </div>

              <div className="form-group-pro">
                <label>Xác nhận mật khẩu mới</label>
                <input
                  type="password"
                  name="confirm_password"
                  value={passwordForm.confirm_password}
                  onChange={handlePasswordChange}
                  placeholder="Nhập lại mật khẩu mới"
                />
              </div>

              <button className="btn-primary-pink">
                <KeyRound size={16} />
                Đổi mật khẩu
              </button>
            </form>
          </div>
        </div>
      </div>

      <div className="card-box mt-4">
        <div className="section-header">
          <h5>Thông tin hệ thống</h5>
          <span>Account metadata</span>
        </div>

        <div className="account-meta-grid">
          <div>
            <span>Ngày tạo</span>
            <strong>{formatDate(account?.created_at)}</strong>
          </div>

          <div>
            <span>Cập nhật gần nhất</span>
            <strong>{formatDate(account?.updated_at)}</strong>
          </div>

          <div>
            <span>Xác thực email lúc</span>
            <strong>{formatDate(account?.email_verified_at)}</strong>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Account;