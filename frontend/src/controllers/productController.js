import axiosClient from "../api/axiosClient";

export const getProductCategoryVideos = async (
  category,
  page = 1,
  pageSize = 50,
  filters = {}
) => {
  return await axiosClient.get(`/api/products/${category}/videos`, {
    params: {
      page,
      page_size: pageSize,
      style: filters.style || "all",
      search: filters.search || "",
      sort_by: filters.sort_by || "views",
    },
  });
};

export const getProductCategories = async () => {
  return await axiosClient.get("/api/products/categories");
};