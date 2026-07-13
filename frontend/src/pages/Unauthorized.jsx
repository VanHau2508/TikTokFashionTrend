import React from "react";
import { Link } from "react-router-dom";
import { ShieldAlert } from "lucide-react";

function Unauthorized() {
  return (
    <div className="error-page">
      <div className="error-card">
        <div className="error-icon">
          <ShieldAlert size={42} />
        </div>
        <h1>Không có quyền truy cập</h1>
        <p>
          Tài khoản của bạn không có quyền truy cập khu vực này. Vui lòng quay
          lại dashboard phù hợp với vai trò của bạn.
        </p>
        <Link to="/" className="btn-primary-pink">
          Quay về trang chính
        </Link>
      </div>
    </div>
  );
}

export default Unauthorized;