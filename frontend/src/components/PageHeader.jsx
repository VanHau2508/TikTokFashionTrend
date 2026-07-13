import React from "react";
import { RefreshCcw, Sparkles } from "lucide-react";

function PageHeader({
  title,
  subtitle,
  badge = "AI-powered analytics",
  onRefresh,
  rightContent,
}) {
  return (
    <div className="page-header-pro">
      <div>
        <div className="page-badge">
          <Sparkles size={15} />
          <span>{badge}</span>
        </div>

        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>

      <div className="page-header-actions">
        {rightContent}

        {onRefresh && (
          <button className="btn-soft-pink" onClick={onRefresh}>
            <RefreshCcw size={16} />
            Làm mới
          </button>
        )}
      </div>
    </div>
  );
}

export default PageHeader;