import axiosClient from "../../api/axiosClient";

const unwrap = (response) => response?.data ?? response;

export const getAdminControlCenter = async () => {
  const response = await axiosClient.get("/api/admin/control-center");
  return unwrap(response);
};

export const getSystemHealth = async () => {
  const response = await axiosClient.get("/api/admin/system-health");
  return unwrap(response);
};

export const getDataQualitySummary = async () => {
  const response = await axiosClient.get("/api/admin/system/data-quality-summary");
  return unwrap(response);
};

export const getModelEvaluation = async () => {
  const response = await axiosClient.get("/api/admin/system/model-evaluation");
  return unwrap(response);
};

export const getPipelineStatus = async () => {
  const response = await axiosClient.get("/api/admin/system/pipeline-status");
  return unwrap(response);
};
