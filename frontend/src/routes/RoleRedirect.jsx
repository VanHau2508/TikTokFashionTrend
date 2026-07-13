import React from "react";
import { Navigate } from "react-router-dom";
import { getLocalUser, isAuthenticated } from "../controllers/authController";

function RoleRedirect() {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  const user = getLocalUser();

  if (user?.role === "admin") {
    return <Navigate to="/admin/dashboard" replace />;
  }

  return <Navigate to="/app/dashboard" replace />;
}

export default RoleRedirect;