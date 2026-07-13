import axiosClient from "../api/axiosClient";

export const getMyAccount = async () => {
  return await axiosClient.get("/api/account/me");
};

export const updateProfile = async (payload) => {
  return await axiosClient.put("/api/account/profile", payload);
};

export const changePassword = async (currentPassword, newPassword) => {
  return await axiosClient.put("/api/account/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
};