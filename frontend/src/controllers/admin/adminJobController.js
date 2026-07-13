import axiosClient from "../../api/axiosClient";

const unwrap = (response) => response?.data ?? response;

export const getCrawlerJobs = async () => {
  const response = await axiosClient.get("/api/admin/crawler-jobs");
  return unwrap(response);
};
