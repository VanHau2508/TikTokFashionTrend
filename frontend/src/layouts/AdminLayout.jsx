import React from "react";
import { Outlet } from "react-router-dom";
import AdminSidebar from "../components/AdminSidebar";
import Header from "../components/Header";

function AdminLayout() {
  return (
    <div className="app-shell admin-shell">
      <AdminSidebar />

      <main className="main-content">
        <Header />
        <div className="page-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export default AdminLayout;