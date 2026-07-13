import React from "react";
import { Navigate } from "react-router-dom";
import { isAuthenticated } from "../controllers/authController";

function PrivateRoute({ children }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

export default PrivateRoute;