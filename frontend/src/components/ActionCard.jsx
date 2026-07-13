import React from "react";
import { PlayCircle, Loader2 } from "lucide-react";

function ActionCard({
  title,
  description,
  icon: Icon,
  buttonText = "Chạy tác vụ",
  loading = false,
  onClick,
  disabled = false,
}) {
  return (
    <div className="action-card">
      <div className="action-icon">
        {Icon ? <Icon size={24} /> : <PlayCircle size={24} />}
      </div>

      <div className="action-content">
        <h5>{title}</h5>
        <p>{description}</p>

        <button
          className="btn-primary-pink"
          onClick={onClick}
          disabled={disabled || loading}
        >
          {loading ? (
            <>
              <Loader2 size={16} className="spin-icon" /> Đang chạy...
            </>
          ) : (
            buttonText
          )}
        </button>
      </div>
    </div>
  );
}

export default ActionCard;