import axiosClient from "../../api/axiosClient";

const unwrap = (response) => response?.data ?? response;

export const getUsers = async () => {
  const response = await axiosClient.get("/api/admin/users");
  return unwrap(response);
};

export const getAdvancedUsers = async ({
  search = "",
  role = "all",
  verified = "all",
  active = "all",
  limit = 100,
} = {}) => {
  const response = await axiosClient.get("/api/admin/users/advanced", {
    params: {
      search,
      role,
      verified,
      active,
      limit,
    },
  });

  return unwrap(response);
};

export const createAdminUser = async (payload) => {
  const response = await axiosClient.post("/api/admin/users", payload);
  return unwrap(response);
};

export const updateAdminUser = async (userId, payload) => {
  const response = await axiosClient.put(`/api/admin/users/${userId}`, payload);
  return unwrap(response);
};

export const updateAdminUserStatus = async (userId, isActive) => {
  const response = await axiosClient.patch(`/api/admin/users/${userId}/status`, {
    is_active: isActive,
  });

  return unwrap(response);
};
