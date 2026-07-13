import axiosClient from "../../api/axiosClient";

const unwrap = (response) => response?.data ?? response;

const cleanParams = (payload = {}) => {
  const result = {};

  Object.entries(payload).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      result[key] = value;
    }
  });

  return result;
};

export const runCrawlHashtags = async (payload) => {
  const response = await axiosClient.post("/api/admin/tasks/crawl-hashtags", payload);
  return unwrap(response);
};

export const runProcessYolo = async (payload = {}) => {
  const response = await axiosClient.post(
    "/api/admin/tasks/process-yolo",
    cleanParams(payload)
  );
  return unwrap(response);
};

export const runSyncStats = async (payload = {}) => {
  const response = await axiosClient.post(
    "/api/admin/tasks/sync-stats",
    cleanParams(payload)
  );
  return unwrap(response);
};

export const runBuildTrendHistory = async (payload = {}) => {
  const response = await axiosClient.post(
    "/api/admin/tasks/build-trend-history",
    cleanParams(payload)
  );
  return unwrap(response);
};

export const runPrediction = async (payload = {}) => {
  const response = await axiosClient.post(
    "/api/admin/tasks/run-prediction",
    cleanParams(payload)
  );
  return unwrap(response);
};

export const runEvaluatePredictions = async (payload = {}) => {
  const response = await axiosClient.post(
    "/api/admin/tasks/evaluate-predictions",
    cleanParams(payload)
  );

  return unwrap(response);
};

export const runBackupDatabase = async (payload = {}) => {
  const response = await axiosClient.post(
    "/api/admin/tasks/backup-database",
    cleanParams(payload)
  );
  return unwrap(response);
};

export const getAdminTaskHistory = async () => {
  const response = await axiosClient.get("/api/admin/tasks/history");
  return unwrap(response);
};

export const getAdminTaskHistoryDb = async () => {
  const response = await axiosClient.get("/api/admin/tasks/history-db");
  return unwrap(response);
};

export const getAdminTaskDetail = async (taskId) => {
  const response = await axiosClient.get(`/api/admin/tasks/${taskId}`);
  return unwrap(response);
};

export const cancelAdminTask = async (taskId) => {
  const response = await axiosClient.post(`/api/admin/tasks/${taskId}/cancel`);
  return unwrap(response);
};
