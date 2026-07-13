import React from "react";
import { BrainCircuit, TrendingUp, Shirt, AlertCircle } from "lucide-react";

function AISummaryPanel({ topTrend, predictedTrend, fashionItem, emergingCount }) {
  const summaries = [
    {
      icon: TrendingUp,
      title: "Hashtag nổi bật",
      text: topTrend
        ? `#${topTrend.tag_name} đang là hashtag có sức hút cao với lượng view lớn nhất trong nhóm dữ liệu hiện tại.`
        : "Chưa có đủ dữ liệu hashtag để phân tích.",
    },
    {
      icon: BrainCircuit,
      title: "Dự đoán AI",
      text: predictedTrend
        ? `LSTM đang dự đoán #${predictedTrend.tag_name} có khả năng tiếp tục tăng trưởng trong kỳ tiếp theo.`
        : "Chưa có dữ liệu dự đoán. Hãy chạy LSTM prediction trong Admin Panel.",
    },
    {
      icon: Shirt,
      title: "Item thời trang",
      text: fashionItem
        ? `${fashionItem.item_type} đang là item được YOLO phát hiện nhiều nhất trong dữ liệu video.`
        : "Chưa có dữ liệu fashion_items từ YOLOv8.",
    },
    {
      icon: AlertCircle,
      title: "Emerging signal",
      text:
        emergingCount > 0
          ? `Hệ thống phát hiện ${emergingCount} xu hướng đang có dấu hiệu tăng trưởng.`
          : "Chưa có emerging trend rõ ràng trong kỳ hiện tại.",
    },
  ];

  return (
    <div className="ai-summary-panel">
      <div className="ai-summary-header">
        <div>
          <span>AI Summary</span>
          <h3>Nhận định nhanh từ hệ thống</h3>
        </div>
        <div className="ai-chip">Rule-based insight</div>
      </div>

      <div className="ai-summary-grid">
        {summaries.map((item) => {
          const Icon = item.icon;

          return (
            <div className="ai-summary-item" key={item.title}>
              <div className="ai-summary-icon">
                <Icon size={20} />
              </div>
              <div>
                <strong>{item.title}</strong>
                <p>{item.text}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default AISummaryPanel;