import React from "react";
function formatNumber(value) {
  if (value === null || value === undefined) return "0";

  const number = Number(value);

  if (number >= 1_000_000_000) return `${(number / 1_000_000_000).toFixed(2)}B`;
  if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(2)}M`;
  if (number >= 1_000) return `${(number / 1_000).toFixed(2)}K`;

  return number.toLocaleString("vi-VN");
}

function StatCard({ title, value, icon: Icon, description, accent = "pink" }) {
  return (
    <div className={`stat-card stat-card-${accent}`}>
      <div className="stat-card-top">
        <div>
          <p>{title}</p>
          <h3>{formatNumber(value)}</h3>
        </div>

        {Icon && (
          <div className="stat-icon">
            <Icon size={24} />
          </div>
        )}
      </div>

      {description && <span className="stat-description">{description}</span>}
    </div>
  );
}

export default StatCard;