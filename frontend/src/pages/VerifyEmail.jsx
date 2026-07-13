import React, { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import toast from "react-hot-toast";
import { ShieldCheck, Mail } from "lucide-react";
import { verifyEmail, resendEmailOtp } from "../controllers/authController";

function VerifyEmail() {
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const [email, setEmail] = useState(params.get("email") || "");
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [devOtp, setDevOtp] = useState("");

  const handleVerify = async (event) => {
    event.preventDefault();

    try {
      setLoading(true);

      const response = await verifyEmail(email, otp);

      toast.success(response.message || "Xác thực email thành công");
      navigate("/login");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Xác thực thất bại");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    try {
      const response = await resendEmailOtp(email, "verify_email");

      if (response.dev_otp) {
        setDevOtp(response.dev_otp);
      }

      toast.success(response.message || "Đã gửi lại OTP");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Không thể gửi lại OTP");
    }
  };

  return (
    <div className="auth-simple-page">
      <div className="auth-simple-card">
        <div className="auth-simple-icon">
          <ShieldCheck size={42} />
        </div>

        <h1>Xác thực email</h1>
        <p>Nhập mã OTP đã được gửi đến Gmail của bạn.</p>

        <form onSubmit={handleVerify}>
          <div className="auth-form-group light">
            <label>Email</label>
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="user@example.com"
            />
          </div>

          <div className="auth-form-group light">
            <label>Mã OTP</label>
            <input
              value={otp}
              onChange={(event) => setOtp(event.target.value)}
              placeholder="Nhập 6 số OTP"
              maxLength={6}
            />
          </div>

          <button className="auth-submit-btn" disabled={loading}>
            {loading ? "Đang xác thực..." : "Xác thực email"}
          </button>
        </form>

        <button className="auth-link-btn" onClick={handleResend}>
          <Mail size={16} />
          Gửi lại mã OTP
        </button>

        <Link to="/login" className="auth-back-link">
          Quay lại đăng nhập
        </Link>
      </div>
    </div>
  );
}

export default VerifyEmail;