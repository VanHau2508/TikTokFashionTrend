import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { KeyRound } from "lucide-react";
import { forgotPassword, resetPassword } from "../controllers/authController";

function ForgotPassword() {
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [devOtp, setDevOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const handleRequestOtp = async (event) => {
    event.preventDefault();

    const normalizedEmail = email.trim().toLowerCase();

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(normalizedEmail)) {
        toast.error("Vui lòng nhập đúng định dạng email");
        return;
    }

    if (!normalizedEmail.endsWith("@gmail.com")) {
        toast.error("Vui lòng nhập địa chỉ Gmail hợp lệ");
        return;
    }

    try {
        const response = await forgotPassword(normalizedEmail);

        toast.success(response.message || "Đã gửi OTP đặt lại mật khẩu");
        setEmail(normalizedEmail);
        setStep(2);
    } catch (error) {
        toast.error(
        error.response?.data?.detail ||
            "Không thể gửi OTP. Vui lòng kiểm tra lại email."
        );
    }
    };

  const handleResetPassword = async (event) => {
    event.preventDefault();

    if (newPassword !== confirmPassword) {
      toast.error("Mật khẩu xác nhận không khớp");
      return;
    }

    try {
      const response = await resetPassword(email, otp, newPassword);

      toast.success(response.message || "Đặt lại mật khẩu thành công");
      navigate("/login");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Đặt lại mật khẩu thất bại");
    }
  };

  return (
    <div className="auth-simple-page">
      <div className="auth-simple-card">
        <div className="auth-simple-icon">
          <KeyRound size={42} />
        </div>

        <h1>Quên mật khẩu</h1>
        <p>
          Nhập Gmail để nhận mã OTP và tạo mật khẩu mới cho tài khoản của bạn.
        </p>

        {step === 1 ? (
          <form onSubmit={handleRequestOtp}>
            <div className="auth-form-group light">
              <label>Email</label>
              <input
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="Nhập email của bạn"
              />
            </div>

            <button className="auth-submit-btn">
              Gửi mã OTP
            </button>
          </form>
        ) : (
          <form onSubmit={handleResetPassword}>
            <div className="auth-form-group light">
              <label>Mã OTP</label>
              <input
                value={otp}
                onChange={(event) => setOtp(event.target.value)}
                placeholder="Nhập 6 số OTP"
                maxLength={6}
              />
            </div>

            <div className="auth-form-group light">
              <label>Mật khẩu mới</label>
              <input
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                placeholder="Nhập mật khẩu mới"
              />
            </div>

            <div className="auth-form-group light">
              <label>Xác nhận mật khẩu</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="Nhập lại mật khẩu mới"
              />
            </div>

            <button className="auth-submit-btn">
              Đặt lại mật khẩu
            </button>
          </form>
        )}

        <Link to="/login" className="auth-back-link">
          Quay lại đăng nhập
        </Link>
      </div>
    </div>
  );
}

export default ForgotPassword;