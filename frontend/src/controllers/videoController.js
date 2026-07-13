import axiosClient from "../api/axiosClient";

export const getTrendingVideos = async (
  page = 1,
  pageSize = 50,
  filters = {}
) => {
  return await axiosClient.get("/api/videos/trending", {
    params: {
      page,
      page_size: pageSize,
      search: filters.search || "",
      status: filters.status || "all",
      item: filters.item || "all",
      sort_by: filters.sort_by || "views",
    },
  });
};

export const getFashionItemOptions = async () => {
  return await axiosClient.get("/api/videos/fashion-items/options");
};

export const getVideoHistory = async (videoId) => {
  return await axiosClient.get(`/api/videos/${videoId}/history`);
};

export const getTopFashionItems = async (limit = 10) => {
  return await axiosClient.get("/api/fashion-items/top", {
    params: {
      limit,
    },
  });
};