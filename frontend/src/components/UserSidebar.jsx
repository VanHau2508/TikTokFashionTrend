import React from "react";
import { BrainCircuit } from "lucide-react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  TrendingUp,
  Video,
  LogOut,
  Sparkles,
  Hash,
  ShoppingBag,
} from "lucide-react";
import { UserCircle } from "lucide-react";
import { logout, getLocalUser } from "../controllers/authController";

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import UserAvatar from "./UserAvatar";
import { getMyAccount } from "../controllers/accountController";

function UserSidebar() {
  const user = getLocalUser();
  const navigate = useNavigate();
  const [account, setAccount] = useState(null);

  useEffect(() => {
    loadAccount();
  }, []);

  const loadAccount = async () => {
    try {
      const data = await getMyAccount();
      setAccount(data);
    } catch (error) {
      console.error("Load sidebar account error:", error);
    }
  };
  useEffect(() => {
  const handleAccountUpdated = () => {
    loadAccount();
  };

  window.addEventListener("account-updated", handleAccountUpdated);

  return () => {
    window.removeEventListener("account-updated", handleAccountUpdated);
  };
}, []);

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-icon">
          <Sparkles size={24} />
        </div>
        <div>
          <h3>FashionTrend</h3>
          <span>User Analytics</span>
        </div>
      </div>

      <button
        className="sidebar-user-card sidebar-user-clickable"
        onClick={() => navigate("/app/account")}
      >
        <UserAvatar user={account} size={52} />

        <div>
          <strong>{account?.username || "user"}</strong>
        </div>
      </button>

      <div className="sidebar-group-title">PHÂN TÍCH</div>
        <NavLink
          to="/app/account"
          className={({ isActive }) =>
            isActive ? "sidebar-link active" : "sidebar-link"
          }
        >
        </NavLink>

      <nav className="sidebar-nav">
        <NavLink
          to="/app/dashboard"
          className={({ isActive }) =>
            isActive ? "sidebar-link active" : "sidebar-link"
          }
        >
          <LayoutDashboard size={20} />
          <span>Tổng quan</span>
        </NavLink>

        <NavLink
          to="/app/trends"
          className={({ isActive }) =>
            isActive ? "sidebar-link active" : "sidebar-link"
          }
        >
          <TrendingUp size={20} />
          <span>Xu hướng</span>
        </NavLink>

        <NavLink
          to="/app/hashtags"
          className={({ isActive }) =>
            isActive ? "sidebar-link active" : "sidebar-link"
          }
        >
          <Hash size={20} />
          <span>Hashtag thịnh hành</span>
        </NavLink>

        <NavLink
          to="/app/products"
          className={({ isActive }) =>
            isActive ? "sidebar-link active" : "sidebar-link"
          }
        >
          <ShoppingBag size={20} />
          <span>Sản phẩm</span>
        </NavLink>

        <NavLink
          to="/app/videos"
          className={({ isActive }) =>
            isActive ? "sidebar-link active" : "sidebar-link"
          }
        >
          <Video size={20} />
          <span>Video thịnh hành</span>
        </NavLink>
         
        <NavLink to="/app/analytics" className="sidebar-link">
          <BrainCircuit size={20} />
          <span>Phân tích AI</span>
        </NavLink>
      </nav>

      <button className="sidebar-logout" onClick={logout}>
        <LogOut size={18} />
        <span>Đăng xuất</span>
      </button>
    </aside>
  );
}

export default UserSidebar;