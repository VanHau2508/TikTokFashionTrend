import React from "react";
import { Inbox } from "lucide-react";

function EmptyState({ title = "Không có dữ liệu", description = "Dữ liệu sẽ hiển thị sau khi hệ thống thu thập và xử lý." }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Inbox size={28} />
      </div>
      <h5>{title}</h5>
      <p>{description}</p>
    </div>
  );
}

export default EmptyState;