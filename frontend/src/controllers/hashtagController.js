import axiosClient from "../api/axiosClient";

// Hàm bổ trợ để loại bỏ các param bị undefined hoặc null (thay thế cho normalizeParams)
const normalizeParams = (params) => {
  const cleanParams = {};
  Object.keys(params).forEach((key) => {
    if (params[key] !== undefined && params[key] !== null && params[key] !== "") {
      cleanParams[key] = params[key];
    }
  });
  return cleanParams;
};

export const getTrendingHashtags = async (limit = 10) => {
  return await axiosClient.get(`/api/hashtags/trending?limit=${limit}`);
};

export const getHashtagDetail = async (hashtagId) => {
  return await axiosClient.get(`/api/hashtags/${hashtagId}`);
};

export const getHashtagVideos = async (hashtagId, page = 1, pageSize = 50) => {
  return await axiosClient.get(`/api/hashtags/${hashtagId}/videos`, {
    params: {
      page,
      page_size: pageSize,
    },
  });
};

// Yêu cầu 14: Đã được tích hợp và export chính xác để Hashtags.jsx sử dụng
export const getPeriodComparison = async ({
  startA,
  endA,
  startB,
  endB,
  limit = 30,
}) => {
  return await axiosClient.get("/api/analytics/period-comparison", {
    params: normalizeParams({
      start_a: startA,
      end_a: endA,
      start_b: startB,
      end_b: endB,
      limit,
    }),
  });
};