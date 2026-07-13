import React from "react";

function InsightCard({ label, title, value, description, icon: Icon, variant = "pink" }) {
  return (
    <div className={`insight-card insight-${variant}`}>
      <div className="insight-top">
        <div>
          <span>{label}</span>
          <h4>{title}</h4>
        </div>

        {Icon && (
          <div className="insight-icon">
            <Icon size={22} />
          </div>
        )}
      </div>

      <strong>{value}</strong>
      <p>{description}</p>
    </div>
  );
}

export default InsightCard;