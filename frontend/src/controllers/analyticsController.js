import axiosClient from "../api/axiosClient";

const normalizeParams = (params = {}) => {
  const result = {};

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      result[key] = value;
    }
  });

  return result;
};

// Yêu cầu 6: keyword/hashtag intelligence
export const getFashionKeywordAnalysis = async ({
  limit = 20,
  hashtagId,
} = {}) => {
  return await axiosClient.get("/api/analytics/fashion-keywords", {
    params: normalizeParams({
      limit,
      hashtag_id: hashtagId,
    }),
  });
};

// Yêu cầu 7: timeline theo hashtag/trend
export const getTrendTimeline = async ({
  hashtagId,
  limit = 5,
} = {}) => {
  return await axiosClient.get("/api/analytics/trend-timeline", {
    params: normalizeParams({
      hashtag_id: hashtagId,
      limit,
    }),
  });
};

// Yêu cầu 8: engagement tổng quan hoặc engagement theo 1 video
export const getEngagementAnalysis = async ({
  limit = 20,
  videoId,
} = {}) => {
  return await axiosClient.get("/api/analytics/engagement", {
    params: {
      limit,
      video_id: videoId || undefined,
    },
  });
};

export const getVideoEngagementAnalysis = async (videoId) => {
  return await getEngagementAnalysis({
    videoId,
    limit: 20,
  });
};

// Yêu cầu 13: prediction LSTM
export const getPredictionSummary = async ({
  limit = 20,
  modelVersion = "lstm_trend_history_growth_v2",
} = {}) => {
  return await axiosClient.get("/api/analytics/prediction-summary", {
    params: normalizeParams({
      limit,
      model_version: modelVersion,
    }),
  });
};

// Yêu cầu 14: giữ lại để dùng ở trang phụ/diagnostic
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

// Yêu cầu 15: lịch sử phân tích
export const getAnalysisHistory = async (limit = 20) => {
  return await axiosClient.get("/api/analytics/analysis-history", {
    params: { limit },
  });
};