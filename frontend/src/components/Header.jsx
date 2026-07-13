import { getLocalUser } from "../controllers/authController";

import React, { useEffect, useRef, useState } from "react";
import { Bell, LogOut, Search, UserCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import UserAvatar from "./UserAvatar";
import { getMyAccount } from "../controllers/accountController";
import { logout } from "../controllers/authController";

function Header() {
  const user = getLocalUser();
  const navigate = useNavigate();
  const dropdownRef = useRef(null);

  const [account, setAccount] = useState(null);
  const [openDropdown, setOpenDropdown] = useState(false);

  useEffect(() => {
    loadAccount();
  }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setOpenDropdown(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const loadAccount = async () => {
    try {
      const data = await getMyAccount();
      setAccount(data);
    } catch (error) {
      console.error("Load header account error:", error);
    }
  };

  const handleLogout = () => {
    logout();
  };

  const goToAccount = () => {
    setOpenDropdown(false);
    navigate("/app/account");
  };

  return (
    <header className="top-header">
      <div>
        <h4>Hệ thống phân tích xu hướng thời trang TikTok</h4>
        <p>Dashboard AI hỗ trợ phân tích, dự đoán và trực quan hóa dữ liệu.</p>
      </div>

      <div className="header-actions">
        <div className="search-box">
          <Search size={18} />
          <input placeholder="Tìm hashtag, video, xu hướng..." />
        </div>

        <button className="icon-button">
          <Bell size={18} />
        </button>

        <div className="header-user-dropdown" ref={dropdownRef}>
          <button
            className="header-user-button"
            onClick={() => setOpenDropdown(!openDropdown)}
          >
            <UserAvatar user={account} size={42} />

            <div>
              <strong>{account?.username || "user"}</strong>
              <span>{account?.role || "user"}</span>
            </div>
          </button>

          {openDropdown && (
            <div className="header-dropdown-menu">
              <button onClick={goToAccount}>
                <UserCircle size={18} />
                Tài khoản của tôi
              </button>

              <button onClick={handleLogout} className="danger">
                <LogOut size={18} />
                Đăng xuất
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

export default Header;