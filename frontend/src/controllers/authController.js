import axiosClient from "../api/axiosClient";

export const login = async (username, password) => {
  const formData = new URLSearchParams();
  formData.append("username", username);
  formData.append("password", password);

  const response = await axiosClient.post("/api/auth/login", formData, {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  });

  const data = response.data || response;

  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("user", JSON.stringify(data.user));

  return data;
};

export const register = async (payload) => {
  const response = await axiosClient.post("/api/auth/register", payload);
  return response.data || response;
};

export const logout = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("user");
  window.location.href = "/login";
};

export const getToken = () => {
  return localStorage.getItem("access_token");
};

export const getLocalUser = () => {
  const raw = localStorage.getItem("user");

  if (!raw) return null;

  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

export const isAuthenticated = () => {
  return Boolean(getToken());
};
export const verifyEmail = async (email, otp) => {
  return await axiosClient.post("/api/auth/verify-email", {
    email,
    otp,
  });
};

export const resendEmailOtp = async (email, purpose = "verify_email") => {
  return await axiosClient.post("/api/auth/resend-email-otp", {
    email,
    purpose,
  });
};

export const forgotPassword = async (email) => {
  return await axiosClient.post("/api/auth/forgot-password", {
    email,
  });
};

export const resetPassword = async (email, otp, newPassword) => {
  return await axiosClient.post("/api/auth/reset-password", {
    email,
    otp,
    new_password: newPassword,
  });
};