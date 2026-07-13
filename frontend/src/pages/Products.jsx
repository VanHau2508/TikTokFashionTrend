import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Mars, Venus, Watch, ArrowRight } from "lucide-react";
import { getProductCategories } from "../controllers/productController";
import EmptyState from "../components/EmptyState";

function formatNumber(value) {
  const numberValue = Number(value || 0);
  if (!Number.isFinite(numberValue)) return "0";
  return Math.round(numberValue).toLocaleString("vi-VN");
}

const ICON_MAP = {
  men: Mars,
  women: Venus,
  accessories: Watch,
};

function Products() {
  const navigate = useNavigate();

  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCategories();
  }, []);

  const loadCategories = async () => {
    try {
      setLoading(true);
      const data = await getProductCategories();
      setCategories(data || []);
    } catch (error) {
      console.error("Product categories error:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading-box">Đang tải danh mục sản phẩm...</div>;
  }

  return (
    <div>
      <h1 className="page-title">Sản phẩm thời trang</h1>
      <p className="page-subtitle">
        Phân loại video theo nhóm sản phẩm: Thời Trang Nam, Thời Trang Nữ và Phụ Kiện.
      </p>

      {categories.length === 0 ? (
        <EmptyState title="Chưa có dữ liệu sản phẩm" />
      ) : (
        <div className="product-category-grid">
          {categories.map((category) => {
            const Icon = ICON_MAP[category.category] || Watch;

            return (
              <div
                className={`product-category-card product-${category.category}`}
                key={category.category}
                onClick={() => navigate(`/app/products/${category.category}`)}
              >
                <div className="product-icon">
                  <Icon size={30} />
                </div>

                <h3>{category.label}</h3>
                <p>{category.description}</p>

                <div className="product-category-metrics">
                  <div>
                    <span>Video</span>
                    <strong>{formatNumber(category.video_count)}</strong>
                  </div>
                  <div>
                    <span>Tổng lượt xem</span>
                    <strong>{formatNumber(category.top_views)}</strong>
                  </div>
                </div>

                <button className="category-open-btn">
                  Xem video <ArrowRight size={16} />
                </button>
              </div>
            );
          })}
        </div>
      )}

      <div className="card-box mt-4">
        <div className="section-header">
          <h5>Gợi ý phân loại</h5>
          <span>Logic hệ thống</span>
        </div>

        <p className="text-muted mb-0">
          Hệ thống phân loại sản phẩm dựa trên hashtag, mô tả video và item được YOLO phát hiện.
          Các nhóm phong cách như streetwear, vintage, Y2K có thể bổ sung sau dưới dạng bộ lọc nâng cao.
        </p>
      </div>
    </div>
  );
}

export default Products;