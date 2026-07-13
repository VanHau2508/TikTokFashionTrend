import axiosClient from "../../api/axiosClient";

const unwrap = (response) => response?.data ?? response;

const cleanParams = (params = {}) => {
  const result = {};

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      result[key] = value;
    }
  });

  return result;
};

export const getAdminVideoSummary = async () => {
  const response = await axiosClient.get("/api/admin/videos/summary");
  return unwrap(response);
};

export const getAdminVideos = async (params = {}) => {
  const response = await axiosClient.get("/api/admin/videos", {
    params: cleanParams(params),
  });
  return unwrap(response);
};

export const getAdminVideoDetail = async (videoId) => {
  const response = await axiosClient.get(`/api/admin/videos/${videoId}`);
  return unwrap(response);
};

export const getAdminFashionItemOptions = async () => {
  const response = await axiosClient.get("/api/admin/videos/fashion-items/options");
  return unwrap(response);
};

export const resetAdminVideosForYolo = async (videoIds, clearOldResults = true) => {
  const response = await axiosClient.post("/api/admin/videos/bulk/reset-yolo", {
    video_ids: videoIds,
    clear_old_results: clearOldResults,
  });
  return unwrap(response);
};

export const markAdminVideosScope = async (
  videoIds,
  isInScope,
  reason = "admin_excluded"
) => {
  const response = await axiosClient.post("/api/admin/videos/bulk/mark-scope", {
    video_ids: videoIds,
    is_in_scope: isInScope,
    reason,
  });
  return unwrap(response);
};

export const updateAdminVideoScope = async (
  videoId,
  isInScope,
  reason = "admin_excluded"
) => {
  const response = await axiosClient.patch(`/api/admin/videos/${videoId}/scope`, {
    is_in_scope: isInScope,
    reason,
  });
  return unwrap(response);
};

export const updateAdminVideoStatus = async (videoId, processingStatus, isAnalyzed) => {
  const payload = { processing_status: processingStatus };

  if (isAnalyzed !== undefined) {
    payload.is_analyzed = isAnalyzed;
  }

  const response = await axiosClient.patch(`/api/admin/videos/${videoId}/status`, payload);
  return unwrap(response);
};

export const archiveAdminVideos = async (videoIds) => {
  const response = await axiosClient.delete("/api/admin/videos/bulk", {
    data: {
      video_ids: videoIds,
      hard_delete: false,
    },
  });
  return unwrap(response);
};

export const hardDeleteAdminVideos = async (videoIds) => {
  const response = await axiosClient.delete("/api/admin/videos/bulk", {
    data: {
      video_ids: videoIds,
      hard_delete: true,
    },
  });
  return unwrap(response);
};

export const archiveAdminVideo = async (videoId) => {
  const response = await axiosClient.delete(`/api/admin/videos/${videoId}`);
  return unwrap(response);
};

export const hardDeleteAdminVideo = async (videoId) => {
  const response = await axiosClient.delete(`/api/admin/videos/${videoId}`, {
    params: { hard_delete: true },
  });
  return unwrap(response);
};

export const getAdminVideoCoverUpdater = async (taskId) => {
  const response = await axiosClient.get(`/api/admin/videos/cover-update/tasks/${taskId}`);
  return unwrap(response);
};

export const startAdminVideoCoverUpdater = async (payload = {}) => {
  const response = await axiosClient.post(
    "/api/admin/videos/cover-update/start",
    cleanParams(payload)
  );

  return unwrap(response);
};