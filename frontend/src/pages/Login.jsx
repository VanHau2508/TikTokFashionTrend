import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import {
  Sparkles,
  BrainCircuit,
  Eye,
  TrendingUp,
  ShieldCheck,
  UserPlus,
  LogIn,
  BarChart3,
} from "lucide-react";

import { login, register } from "../controllers/authController";

function Login() {
  const navigate = useNavigate();

  const [mode, setMode] = useState("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [loginForm, setLoginForm] = useState({});

  const [registerForm, setRegisterForm] = useState({
    username: "",
    email: "",
    full_name: "",
    password: "",
    confirm_password: "",
  });

  const handleLoginChange = (event) => {
    setLoginForm({
      ...loginForm,
      [event.target.name]: event.target.value,
    });
  };

  const handleRegisterChange = (event) => {
    setRegisterForm({
      ...registerForm,
      [event.target.name]: event.target.value,
    });
  };

  const fillDemo = (username, password) => {
    navigate(`/verify-email?email=${encodeURIComponent(registerForm.email)}`);
    setLoginForm({ username, password });
  };

  const handleLoginSubmit = async (event) => {
    event.preventDefault();

    try {
      setLoading(true);
      setError("");

      const response = await login(loginForm.username, loginForm.password);

      toast.success("Đăng nhập thành công");

      if (response.user?.role === "admin") {
        navigate("/admin/dashboard");
      } else {
        navigate("/app/dashboard");
      }
    } catch (err) {
      const message = err.response?.data?.detail || "Đăng nhập thất bại";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSubmit = async (event) => {
    event.preventDefault();

    if (registerForm.password !== registerForm.confirm_password) {
      setError("Mật khẩu xác nhận không khớp");
      toast.error("Mật khẩu xác nhận không khớp");
      return;
    }

    try {
      setLoading(true);
      setError("");

      await register({
        username: registerForm.username,
        email: registerForm.email,
        full_name: registerForm.full_name,
        password: registerForm.password,
      });

      toast.success("Đăng ký thành công. Bạn có thể đăng nhập.");

      navigate(`/verify-email?email=${encodeURIComponent(registerForm.email)}`);
      setLoginForm({
        username: registerForm.username,
        password: registerForm.password,
      });
    } catch (err) {
      const message = err.response?.data?.detail || "Đăng ký thất bại";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-landing-page">
      <div className="auth-bg-animation">
        <div className="auth-blob" />
        <div className="auth-blob secondary" />
      </div>

      <nav className="auth-nav">
        <div className="auth-logo">
          <div className="auth-logo-icon">
            <Sparkles size={22} />
          </div>
          <div>
            <strong>FashionTrend AI</strong>
            <span>TikTok Fashion Analytics</span>
          </div>
        </div>

        <div className="auth-nav-links">
          <a href="#features">Tính năng</a>
          <a href="#system">Hệ thống</a>
          <a href="#stats">Dữ liệu</a>
          <button onClick={() => setMode("login")}>Đăng nhập</button>
        </div>
      </nav>

      <main className="auth-hero">
        <section className="auth-hero-content">
          <div className="auth-badge">
            <Sparkles size={15} />
            AI-powered Fashion Intelligence
          </div>

          <h1>
            Dẫn đầu xu hướng
            <br />
            <span>TikTok Fashion</span>
          </h1>

          <p>
            Hệ thống hỗ trợ thu thập, phân tích và dự đoán xu hướng thời trang
            TikTok bằng Web Scraping, YOLOv8, NLP và LSTM.
          </p>

          <div className="auth-cta-group">
            <button className="auth-main-btn" onClick={() => setMode("register")}>
              Bắt đầu ngay
            </button>

            <a href="#features" className="auth-outline-btn">
              Khám phá thêm
            </a>
          </div>

          <div className="auth-metric-grid">
            <div>
              <strong>YOLOv8</strong>
              <span>Nhận diện item thời trang</span>
            </div>
            <div>
              <strong>LSTM</strong>
              <span>Dự đoán tăng trưởng xu hướng</span>
            </div>
            <div>
              <strong>Dashboard</strong>
              <span>Trực quan hóa dữ liệu</span>
            </div>
          </div>
        </section>

        <section className="auth-card">
          <div className="auth-card-header">
            <div>
              <span>Welcome back</span>
              <h2>{mode === "login" ? "Đăng nhập" : "Tạo tài khoản"}</h2>
            </div>

            <div className="auth-card-icon">
              {mode === "login" ? <LogIn size={22} /> : <UserPlus size={22} />}
            </div>
          </div>

          <div className="auth-tabs">
            <button
              className={mode === "login" ? "active" : ""}
              onClick={() => {
                setMode("login");
                setError("");
              }}
            >
              Đăng nhập
            </button>

            <button
              className={mode === "register" ? "active" : ""}
              onClick={() => {
                setMode("register");
                setError("");
              }}
            >
              Đăng ký
            </button>
          </div>

          {error && <div className="auth-error">{error}</div>}

          {mode === "login" ? (
            <form onSubmit={handleLoginSubmit}>
              <div className="auth-form-group">
                <label>Tên đăng nhập</label>
                <input
                  name="username"
                  value={loginForm.username}
                  onChange={handleLoginChange}
                  placeholder="Nhập tài khoản"
                />
              </div>

              <div className="auth-form-group">
                <label>Mật khẩu</label>
                <input
                  type="password"
                  name="password"
                  value={loginForm.password}
                  onChange={handleLoginChange}
                  placeholder="Nhập mật khẩu"
                />
                  <div style={{ textAlign: 'right', width: '100%' }}>
                  <Link to="/forgot-password" className="auth-forgot-link"> 
                    Quên mật khẩu? 
                  </Link>
                </div>
              </div>

              <button className="auth-submit-btn" disabled={loading}>
                {loading ? "Đang đăng nhập..." : "Đăng nhập vào hệ thống"}
              </button>

            </form>
          ) : (
            <form onSubmit={handleRegisterSubmit}>
              <div className="auth-form-group">
                <label>Tên đăng nhập</label>
                <input
                  name="username"
                  value={registerForm.username}
                  onChange={handleRegisterChange}
                  placeholder="Nhập tên tài khoản"
                />
              </div>

              <div className="auth-form-group">
                <label>Email</label>
                <input
                  type="email"
                  name="email"
                  value={registerForm.email}
                  onChange={handleRegisterChange}
                  placeholder="Nhập địa chỉ email"
                />
              </div>

              <div className="auth-form-group">
                <label>Họ tên</label>
                <input
                  name="full_name"
                  value={registerForm.full_name}
                  onChange={handleRegisterChange}
                  placeholder="Nhập họ tên"
                />
              </div>

              <div className="auth-form-row">
                <div className="auth-form-group">
                  <label>Mật khẩu</label>
                  <input
                    type="password"
                    name="password"
                    value={registerForm.password}
                    onChange={handleRegisterChange}
                    placeholder="Mật khẩu"
                  />
                </div>

                <div className="auth-form-group">
                  <label>Xác nhận</label>
                  <input
                    type="password"
                    name="confirm_password"
                    value={registerForm.confirm_password}
                    onChange={handleRegisterChange}
                    placeholder="Nhập lại"
                  />
                </div>
              </div>

              <button className="auth-submit-btn" disabled={loading}>
                {loading ? "Đang tạo tài khoản..." : "Đăng ký tài khoản"}
              </button>

              <p className="auth-small-text">
                Tài khoản mới sẽ được cấp quyền người dùng. Admin có thể quản lý
                vai trò trong Admin Panel.
              </p>
            </form>
          )}
        </section>
      </main>

      <section id="features" className="auth-feature-section">
        <div className="auth-section-title">
          <span>Core features</span>
          <h2>Nền tảng phân tích thời trang TikTok</h2>
        </div>

        <div className="auth-feature-grid">
          <div>
            <BarChart3 size={34} />
            <h3>Phân tích xu hướng</h3>
            <p>Thống kê top hashtag, emerging trends và predicted trends.</p>
          </div>

          <div>
            <BrainCircuit size={34} />
            <h3>Dự đoán LSTM</h3>
            <p>Học từ chuỗi thời gian tương tác để dự đoán growth tiếp theo.</p>
          </div>

          <div>
            <Eye size={34} />
            <h3>YOLOv8 Vision</h3>
            <p>Nhận diện item thời trang trong video và lọc dữ liệu usable.</p>
          </div>
        </div>
      </section>

      <section id="system" className="auth-system-section">
        <div className="auth-system-content">
          <div>
            <span className="auth-badge small">How it works</span>
            <h2>Quy trình phân tích thông minh</h2>

            <div className="auth-step">
              <b>01</b>
              <div>
                <h4>Crawl TikTok Hashtags</h4>
                <p>Thu thập video từ các hashtag thời trang như phoidonam, phoidonu.</p>
              </div>
            </div>

            <div className="auth-step">
              <b>02</b>
              <div>
                <h4>YOLOv8 + Video Stats</h4>
                <p>Lọc video có nội dung thời trang và đồng bộ lượt xem, like, comment, share.</p>
              </div>
            </div>

            <div className="auth-step">
              <b>03</b>
              <div>
                <h4>LSTM Prediction</h4>
                <p>Dự đoán xu hướng tăng trưởng và hiển thị lên dashboard.</p>
              </div>
            </div>
          </div>

          <div className="auth-system-visual">
            <div className="auth-pulse" />
            <ShieldCheck size={64} />
            <strong>AI Engine Core</strong>
            <span>Secure · Scalable · Insightful</span>
          </div>
        </div>
      </section>

      <section id="stats" className="auth-stats-section">
        <div>
          <strong>5K+</strong>
          <span>Videos crawled</span>
        </div>
        <div>
          <strong>25+</strong>
          <span>Fashion hashtags</span>
        </div>
        <div>
          <strong>YOLOv8</strong>
          <span>Vision model</span>
        </div>
        <div>
          <strong>LSTM</strong>
          <span>Prediction model</span>
        </div>
      </section>

      <footer className="auth-footer">
        <span>© 2026 FashionTrend AI Analytics</span>
        <div>
          <Link to="/login">Login</Link>
          <Link to="/">Dashboard</Link>
        </div>
      </footer>
    </div>
  );
}

export default Login;