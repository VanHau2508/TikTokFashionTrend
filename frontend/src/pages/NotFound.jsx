import React from "react";
import { Link } from "react-router-dom";
import { SearchX } from "lucide-react";

function NotFound() {
  return (
    <div className="error-page">
      <div className="error-card">
        <div className="error-icon">
          <SearchX size={42} />
        </div>
        <h1>404</h1>
        <p>Trang bạn đang truy cập không tồn tại hoặc đã bị thay đổi đường dẫn.</p>
        <Link to="/" className="btn-primary-pink">
          Quay về dashboard
        </Link>
      </div>
    </div>
  );
}

export default NotFound;