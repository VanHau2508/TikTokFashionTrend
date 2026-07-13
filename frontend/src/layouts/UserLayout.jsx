import React from "react";
import { Outlet } from "react-router-dom";
import UserSidebar from "../components/UserSidebar";
import Header from "../components/Header";

function UserLayout() {
  return (
    <div className="app-shell">
      <UserSidebar />

      <main className="main-content">
        <Header />
        <div className="page-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export default UserLayout;