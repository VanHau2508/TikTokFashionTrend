import axiosClient from "../api/axiosClient";

const unwrap = (response) => response?.data ?? response;

export const getTopTrends = async (limit = 20) => {
  const response = await axiosClient.get("/api/trends/top", {
    params: { limit },
  });

  return unwrap(response);
};

export const getEmergingTrends = async (limit = 20, minVideoCount = 5) => {
  const response = await axiosClient.get("/api/trends/emerging", {
    params: {
      limit,
      min_video_count: minVideoCount,
    },
  });

  return unwrap(response);
};

export const getPredictedTrends = async (limit = 20) => {
  const response = await axiosClient.get("/api/trends/predicted", {
    params: { limit },
  });

  return unwrap(response);
};

export const getTrendHistory = async (hashtagId) => {
  const response = await axiosClient.get(`/api/trends/history/${hashtagId}`);
  return unwrap(response);
};