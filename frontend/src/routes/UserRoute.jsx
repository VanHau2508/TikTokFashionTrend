import React from "react";
import { Navigate } from "react-router-dom";
import { getLocalUser, isAuthenticated } from "../controllers/authController";

function UserRoute({ children }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  const user = getLocalUser();

  if (user?.role === "admin") {
    return <Navigate to="/admin/dashboard" replace />;
  }

  return children;
}

export default UserRoute;