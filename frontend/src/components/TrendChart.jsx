import React, { useMemo, useState } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line, Bar } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Tooltip,
  Legend,
  Filler
);

const RANGE_OPTIONS = [
  { key: "today", label: "Hôm nay" },
  { key: "3d", label: "3 ngày" },
  { key: "7d", label: "7 ngày" },
  { key: "all", label: "Tất cả" },
];

function isValidDate(value) {
  const date = new Date(value);
  return !Number.isNaN(date.getTime());
}

function filterIndexesByRange(dateValues = [], range = "all", total = 0) {
  if (range === "all") {
    return Array.from({ length: total }, (_, index) => index);
  }

  const now = new Date();
  let startDate = null;

  if (range === "today") {
    startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  }

  if (range === "3d") {
    startDate = new Date(now);
    startDate.setDate(startDate.getDate() - 3);
  }

  if (range === "7d") {
    startDate = new Date(now);
    startDate.setDate(startDate.getDate() - 7);
  }

  const hasValidDates =
    dateValues.length > 0 && dateValues.some((item) => isValidDate(item));

  if (hasValidDates && startDate) {
    const indexes = dateValues
      .map((value, index) => {
        const date = new Date(value);
        return date >= startDate ? index : null;
      })
      .filter((index) => index !== null);

    if (indexes.length > 0) return indexes;
  }

  const fallbackMap = {
    today: 3,
    "3d": 6,
    "7d": 12,
  };

  const take = fallbackMap[range] || total;
  const start = Math.max(0, total - take);

  return Array.from({ length: total - start }, (_, index) => start + index);
}

function isSecondaryMetric(label = "") {
  const text = String(label).toLowerCase();

  return (
    text.includes("growth") ||
    text.includes("engagement") ||
    text.includes("rate") ||
    text.includes("tăng")
  );
}

function formatTooltipLabel(context) {
  const label = context.dataset.label || "";
  const value = Number(context.raw || 0);
  const lower = label.toLowerCase();

  if (lower.includes("rate") || lower.includes("engagement")) {
    return `${label}: ${value.toFixed(2)}%`;
  }

  return `${label}: ${value.toLocaleString("vi-VN")}`;
}

function TrendChart({
  title,
  labels = [],
  datasets = [],
  type = "line",
  dateValues = [],
  enableTimeFilter = false,
  enableTypeToggle = false,
  enableSmartAxis = false,
  description = "Biểu đồ phân tích",
}) {
  const [range, setRange] = useState("all");
  const [chartType, setChartType] = useState(type);

  const filteredChart = useMemo(() => {
    const indexes = enableTimeFilter
      ? filterIndexesByRange(dateValues, range, labels.length)
      : Array.from({ length: labels.length }, (_, index) => index);

    const filteredLabels = indexes.map((index) => labels[index]);

    const filteredDatasets = datasets.map((dataset) => {
      const explicitAxis = dataset.yAxisID;
      const shouldUseY1 = explicitAxis
        ? explicitAxis === "y1"
        : enableSmartAxis && isSecondaryMetric(dataset.label || "");

      const {
        type: _ignoredType,
        data,
        ...datasetConfig
      } = dataset;

      const baseDataset = {
        ...datasetConfig,
        data: indexes.map((index) => data?.[index] ?? 0),
        yAxisID: shouldUseY1 ? "y1" : "y",
      };

      if (chartType === "bar") {
        return {
          ...baseDataset,
          borderWidth: dataset.borderWidth ?? 2,
          borderRadius: dataset.borderRadius ?? 10,
          borderSkipped: false,
          categoryPercentage: 0.72,
          barPercentage: 0.82,
          fill: false,
        };
      }

      return {
        ...baseDataset,
        borderWidth: dataset.borderWidth ?? 3,
        pointRadius: dataset.pointRadius ?? 4,
        pointHoverRadius: dataset.pointHoverRadius ?? 6,
        tension: dataset.tension ?? 0.35,
        fill: dataset.fill ?? true,
      };
    });

    return {
      labels: filteredLabels,
      datasets: filteredDatasets,
    };
  }, [
    labels,
    datasets,
    dateValues,
    range,
    chartType,
    enableTimeFilter,
    enableSmartAxis,
  ]);

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: "index",
      intersect: false,
    },
    plugins: {
      legend: {
        position: "bottom",
        labels: {
          usePointStyle: true,
          boxWidth: 8,
          padding: 18,
          color: "#1f283c",
          font: {
            weight: "bold",
          },
        },
      },
      tooltip: {
        backgroundColor: "#1f283c",
        titleColor: "#ffffff",
        bodyColor: "#ffffff",
        borderColor: "#fe2062",
        borderWidth: 1,
        padding: 12,
        cornerRadius: 12,
        callbacks: {
          label: formatTooltipLabel,
        },
      },
    },
    scales: {
      x: {
        grid: {
          display: false,
        },
        ticks: {
          color: "#667d98",
          maxRotation: 35,
          minRotation: 0,
          font: {
            weight: "bold",
          },
        },
      },
      y: {
        beginAtZero: true,
        position: "left",
        grid: {
          color: "rgba(229, 231, 235, 0.85)",
        },
        ticks: {
          color: "#667d98",
          callback: (value) => Number(value || 0).toLocaleString("vi-VN"),
        },
      },
      y1: {
        beginAtZero: true,
        display: enableSmartAxis,
        position: "right",
        grid: {
          drawOnChartArea: false,
        },
        ticks: {
          color: "#42bfc1",
          callback: (value) => Number(value || 0).toLocaleString("vi-VN"),
        },
      },
    },
  };

  return (
    <div className="card-box chart-card h-100">
      <div className="section-header chart-header-pro">
        <div>
          <h5>{title}</h5>
          <span>{description}</span>
        </div>

        <div className="chart-tools">
          {enableTimeFilter && (
            <div className="chart-range-tabs">
              {RANGE_OPTIONS.map((item) => (
                <button
                  key={item.key}
                  className={range === item.key ? "active" : ""}
                  onClick={() => setRange(item.key)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}

          {enableTypeToggle && (
            <div className="chart-type-toggle">
              <button
                className={chartType === "line" ? "active" : ""}
                onClick={() => setChartType("line")}
              >
                Line
              </button>

              <button
                className={chartType === "bar" ? "active" : ""}
                onClick={() => setChartType("bar")}
              >
                Bar
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="chart-container">
        {chartType === "bar" ? (
          <Bar data={filteredChart} options={options} />
        ) : (
          <Line data={filteredChart} options={options} />
        )}
      </div>
    </div>
  );
}

export default TrendChart;
