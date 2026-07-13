import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "react-hot-toast";

import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Trends from "./pages/Trends";
import Videos from "./pages/Videos";
import Analytics from "./pages/Analytics";
import VideoDetailPage from "./pages/VideoDetailPage";

import AdminDashboard from "./pages/admin/AdminDashboard";
import AdminUsers from "./pages/admin/AdminUsers";
import AdminJobs from "./pages/admin/AdminJobs";
import AdminTasks from "./pages/admin/AdminTasks";
import AdminVideoManagement from "./pages/admin/AdminVideoManagement";

import UserLayout from "./layouts/UserLayout";
import AdminLayout from "./layouts/AdminLayout";

import RoleRedirect from "./routes/RoleRedirect";
import UserRoute from "./routes/UserRoute";
import AdminRoute from "./routes/AdminRoute";

import Hashtags from "./pages/Hashtags";
import HashtagDetail from "./pages/HashtagDetail";
import Products from "./pages/Products";
import ProductCategory from "./pages/ProductCategory";
import Unauthorized from "./pages/Unauthorized";
import NotFound from "./pages/NotFound";

import VerifyEmail from "./pages/VerifyEmail";
import ForgotPassword from "./pages/ForgotPassword";
import Account from "./pages/Account";

function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 2800,
          style: {
            borderRadius: "14px",
            background: "#1F283C",
            color: "#fff",
            fontWeight: 700,
          },
          success: {
            iconTheme: {
              primary: "#42FFF6",
              secondary: "#1F283C",
            },
          },
          error: {
            iconTheme: {
              primary: "#FE2062",
              secondary: "#fff",
            },
          },
        }}
      />

      <Routes>
        <Route path="/" element={<RoleRedirect />} />
        <Route path="/login" element={<Login />} />
        <Route path="/unauthorized" element={<Unauthorized />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />

        <Route
          path="/app"
          element={
            <UserRoute>
              <UserLayout />
            </UserRoute>
          }
        >
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="trends" element={<Trends />} />
          <Route path="videos" element={<Videos />} />
          <Route path="videos/:videoId" element={<VideoDetailPage />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="hashtags" element={<Hashtags />} />
          <Route path="hashtags/:hashtagId" element={<HashtagDetail />} />
          <Route path="products" element={<Products />} />
          <Route path="products/:category" element={<ProductCategory />} />
          <Route path="account" element={<Account />} />
        </Route>

        <Route
          path="/admin"
          element={
            <AdminRoute>
              <AdminLayout />
            </AdminRoute>
          }
        >
          <Route path="dashboard" element={<AdminDashboard />} />
          <Route path="users" element={<AdminUsers />} />
          <Route path="videos" element={<AdminVideoManagement />} />
          <Route path="jobs" element={<AdminJobs />} />
          <Route path="tasks" element={<AdminTasks />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
