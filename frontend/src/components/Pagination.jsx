import React from "react";

function Pagination({ page, totalPages, onPageChange }) {
  if (!totalPages || totalPages <= 1) return null;

  const pages = [];

  const start = Math.max(1, page - 2);
  const end = Math.min(totalPages, page + 2);

  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  return (
    <div className="pagination-pro">
      <button
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        Trước
      </button>

      {page > 3 && (
        <>
          <button onClick={() => onPageChange(1)}>1</button>
          <span>...</span>
        </>
      )}

      {pages.map((item) => (
        <button
          key={item}
          className={item === page ? "active" : ""}
          onClick={() => onPageChange(item)}
        >
          {item}
        </button>
      ))}

      {page < totalPages - 2 && (
        <>
          <span>...</span>
          <button onClick={() => onPageChange(totalPages)}>
            {totalPages}
          </button>
        </>
      )}

      <button
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        Sau
      </button>
    </div>
  );
}

export default Pagination;