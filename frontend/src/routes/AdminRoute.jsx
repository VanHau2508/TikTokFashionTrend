import React from "react";
import { Navigate } from "react-router-dom";
import { getLocalUser, isAuthenticated } from "../controllers/authController";

function AdminRoute({ children }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  const user = getLocalUser();

  if (user?.role !== "admin") {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
}

export default AdminRoute;