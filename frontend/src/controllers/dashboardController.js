import axiosClient from "../api/axiosClient";

const unwrap = (response) => response?.data ?? response;

export const getDashboardSummary = async () => {
  const response = await axiosClient.get("/api/dashboard/summary");
  return unwrap(response);
};

export const getStatusDistribution = async () => {
  const response = await axiosClient.get("/api/dashboard/status-distribution");
  return unwrap(response);
};