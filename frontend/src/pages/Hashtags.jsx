import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getTrendingHashtags,
  getPeriodComparison,
} from "../controllers/hashtagController";
import EmptyState from "../components/EmptyState";

function formatNumber(value, options = {}) {
  const {
    decimals = 0,
    compact = false,
    sign = false,
  } = options;

  const numberValue = Number(value || 0);

  if (!Number.isFinite(numberValue)) return "0";

  const displayValue =
    decimals === 0 ? Math.round(numberValue) : numberValue;

  const formatted = displayValue.toLocaleString("vi-VN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    notation: compact ? "compact" : "standard",
  });

  return sign && displayValue > 0 ? `+${formatted}` : formatted;
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(2)}%`;
}

function getViews(tag) {
  return tag.total_views ?? tag.view_count ?? tag.views ?? 0;
}

function getVideoCount(tag) {
  return tag.total_videos ?? tag.video_count ?? tag.total ?? 0;
}

function getGrowth(tag) {
  return tag.view_growth ?? tag.growth_rate ?? 0;
}

function getScore(tag) {
  return tag.trend_score ?? tag.trending_score ?? 0;
}

const getTodayString = () => {
  const today = new Date();
  const offset = today.getTimezoneOffset();
  const localToday = new Date(today.getTime() - offset * 60 * 1000);
  return localToday.toISOString().split("T")[0];
};

function Hashtags() {
  const navigate = useNavigate();

  const MIN_DATE = "2026-05-10";
  const [maxDate, setMaxDate] = useState(getTodayString());

  const [hashtags, setHashtags] = useState([]);
  const [loading, setLoading] = useState(true);

  const [comparisonItems, setComparisonItems] = useState([]);
  const [loadingComp, setLoadingComp] = useState(false);

  const [periodForm, setPeriodForm] = useState({
    startA: "2026-05-10",
    endA: "2026-05-13",
    startB: "2026-05-14",
    endB: getTodayString(),
  });

  useEffect(() => {
    loadHashtagsAndComparison();
  }, []);

  const loadHashtagsAndComparison = async () => {
    try {
      setLoading(true);

      const response = await getTrendingHashtags(10);
      const data = response?.data || response;

      const items = Array.isArray(data) ? data : data?.items || [];
      setHashtags(items);

      const dbMaxDate =
        data?.max_date_in_db ||
        data?.latest_date ||
        items?.[0]?.date ||
        getTodayString();

      setMaxDate(dbMaxDate);

      const nextForm = {
        startA: "2026-05-10",
        endA: "2026-05-13",
        startB: "2026-05-14",
        endB: dbMaxDate,
      };

      setPeriodForm(nextForm);

      await loadComparisonWithForm(nextForm, dbMaxDate, true);
    } catch (error) {
      console.error("Hashtags error:", error);
      setHashtags([]);
      setComparisonItems([]);
    } finally {
      setLoading(false);
    }
  };

  const loadComparisonWithForm = async (
    form,
    currentMaxDate = maxDate,
    silent = false
  ) => {
    if (
      form.startA < MIN_DATE ||
      form.endA > currentMaxDate ||
      form.startB < MIN_DATE ||
      form.endB > currentMaxDate
    ) {
      const message = `Vui lòng chọn ngày trong khoảng từ ${MIN_DATE} đến ${currentMaxDate}`;

      if (silent) {
        console.warn(message);
      } else {
        alert(message);
      }

      return;
    }

    if (form.startA > form.endA) {
      alert("Giai đoạn A: ngày bắt đầu không thể lớn hơn ngày kết thúc.");
      return;
    }

    if (form.startB > form.endB) {
      alert("Giai đoạn B: ngày bắt đầu không thể lớn hơn ngày kết thúc.");
      return;
    }

    try {
      setLoadingComp(true);

      const response = await getPeriodComparison({
        startA: form.startA,
        endA: form.endA,
        startB: form.startB,
        endB: form.endB,
        limit: 10,
      });

      const data = response?.data?.items || response?.items || [];
      setComparisonItems(data);
    } catch (error) {
      console.error("Comparison error:", error);
      setComparisonItems([]);
    } finally {
      setLoadingComp(false);
    }
  };

  const loadComparison = async () => {
    await loadComparisonWithForm(periodForm, maxDate, false);
  };

  const handlePeriodChange = (event) => {
    const { name, value } = event.target;
    setPeriodForm((prev) => ({ ...prev, [name]: value }));
  };

  if (loading) {
    return <div className="loading-box">Đang tải dữ liệu hashtag...</div>;
  }

  return (
    <div
      className="container-fluid py-4"
      style={{ maxWidth: "1200px", margin: "0 auto" }}
    >
      <section className="mb-5">
        <h1 className="page-title">Hashtag thịnh hành</h1>
        <p className="page-subtitle">
          Bảng xếp hạng top 10 hashtag thời trang theo tổng lượt xem, số lượng
          video, lượt xem tăng thêm thực tế và điểm xu hướng hiện tại.
        </p>

        {hashtags.length === 0 ? (
          <EmptyState
            title="Chưa có hashtag thịnh hành"
            description="Hãy build trend_history để hệ thống thống kê top hashtag."
          />
        ) : (
          <div className="hashtag-rank-list">
            {hashtags.map((tag, index) => (
              <div className="hashtag-rank-row" key={tag.hashtag_id}>
                <div className="hashtag-rank-number">#{index + 1}</div>

                <div className="hashtag-rank-main">
                  <h3>#{tag.tag_name}</h3>
                  <p>
                    {formatNumber(getViews(tag))} lượt xem ·{" "}
                    {formatNumber(getVideoCount(tag))} video
                  </p>

                  <div className="hashtag-growth-bar">
                    <div
                      style={{
                        width: `${Math.min(
                          100,
                          (Number(getScore(tag) || 0) / 600000) * 100
                        )}%`,
                      }}
                    />
                  </div>
                </div>

                <div className="hashtag-rank-stats">
                  <span>Lượt xem tăng thêm</span>
                  <strong>{formatNumber(getGrowth(tag))}</strong>
                </div>

                <div className="hashtag-rank-stats">
                  <span>Điểm xu hướng</span>
                  <strong>{formatNumber(getScore(tag))}</strong>
                </div>

                <button
                  className="hashtag-detail-btn"
                  onClick={() => navigate(`/app/hashtags/${tag.hashtag_id}`)}
                >
                  Xem chi tiết
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <hr className="my-5" style={{ opacity: 0.15 }} />

      <section className="analytics-section">
        <div className="section-header mb-4">
          <div>
            <h2 className="h4 fw-bold text-dark">
              So sánh xu hướng giữa các giai đoạn
            </h2>
            <p className="text-muted small">
              Phân tích sự thay đổi của lượt xem tăng thêm thực tế, điểm xu hướng và tỷ
              lệ tương tác để phát hiện hashtag đang bứt phá.
            </p>
            <p className="text-muted small mb-0">
              Dữ liệu hiện có từ {MIN_DATE} đến {maxDate}.
            </p>
          </div>
        </div>

        <div className="period-filter-card p-4 mb-4 card-box shadow-sm">
          <div className="period-inputs-row">
            <div className="period-input-group">
              <label className="form-label small fw-bold">
                Giai đoạn A - Từ ngày
              </label>
              <input
                type="date"
                className="form-control"
                name="startA"
                min={MIN_DATE}
                max={maxDate}
                value={periodForm.startA}
                onChange={handlePeriodChange}
              />
            </div>

            <div className="period-input-group">
              <label className="form-label small fw-bold">
                Giai đoạn A - Đến ngày
              </label>
              <input
                type="date"
                className="form-control"
                name="endA"
                min={MIN_DATE}
                max={maxDate}
                value={periodForm.endA}
                onChange={handlePeriodChange}
              />
            </div>

            <div className="period-input-group">
              <label className="form-label small fw-bold">
                Giai đoạn B - Từ ngày
              </label>
              <input
                type="date"
                className="form-control"
                name="startB"
                min={MIN_DATE}
                max={maxDate}
                value={periodForm.startB}
                onChange={handlePeriodChange}
              />
            </div>

            <div className="period-input-group">
              <label className="form-label small fw-bold">
                Giai đoạn B - Đến ngày
              </label>
              <input
                type="date"
                className="form-control"
                name="endB"
                min={MIN_DATE}
                max={maxDate}
                value={periodForm.endB}
                onChange={handlePeriodChange}
              />
            </div>
          </div>

          <div className="period-actions-row">
            <button
              className="btn-primary-pink"
              onClick={loadComparison}
              disabled={loadingComp}
            >
              {loadingComp ? "Đang xử lý..." : "So sánh ngay"}
            </button>
          </div>
        </div>

        {comparisonItems.length === 0 ? (
          <EmptyState title="Chưa có dữ liệu so sánh cho giai đoạn này" />
        ) : (
          <div
            className="analytics-table-wrap card-box shadow-sm p-0"
            style={{ overflowX: "auto" }}
          >
            <table
              className="table align-middle analytics-table mb-0"
              style={{ width: "100%", borderCollapse: "collapse" }}
            >
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "2px solid #eee" }}>
                  <th style={{ padding: "12px" }}>Hashtag</th>
                  <th style={{ padding: "12px" }}>Lượt xem tăng thêm giai đoạn A</th>
                  <th style={{ padding: "12px" }}>Lượt xem tăng thêm giai đoạn B</th>
                  <th style={{ padding: "12px" }}>Chênh lệch lượt tăng</th>
                  <th style={{ padding: "12px" }}>Độ tăng giảm tương tác</th>
                  <th style={{ padding: "12px" }}>Δ Trend Score</th>
                </tr>
              </thead>
              <tbody>
                {comparisonItems.map((item) => (
                  <tr
                    key={item.hashtag_id}
                    style={{ borderBottom: "1px solid #eee" }}
                  >
                    <td style={{ padding: "12px" }}>
                      <span
                        className="text-primary fw-bold"
                        style={{ cursor: "pointer", color: "#0d6efd" }}
                        onClick={() =>
                          navigate(`/app/hashtags/${item.hashtag_id}`)
                        }
                      >
                        #{item.tag_name}
                      </span>
                    </td>

                    <td style={{ padding: "12px" }}>
                      {formatNumber(item.period_a?.total_view_growth)}
                    </td>

                    <td style={{ padding: "12px" }}>
                      {formatNumber(item.period_b?.total_view_growth)}
                    </td>

                    <td style={{ padding: "12px" }}>
                      <span
                        className={
                          item.delta_total_view_growth >= 0
                            ? "badge-green"
                            : "badge-red"
                        }
                      >
                        {item.delta_total_view_growth >= 0 ? "+" : ""}
                        {formatNumber(item.delta_total_view_growth)}
                      </span>
                    </td>

                    <td style={{ padding: "12px" }}>
                      <span
                        className={
                          item.delta_engagement_rate >= 0
                            ? "text-success"
                            : "text-danger"
                        }
                      >
                        {item.delta_engagement_rate >= 0 ? "+" : ""}
                        {formatPercent(item.delta_engagement_rate)}
                      </span>
                    </td>

                    <td style={{ padding: "12px" }}>
                      <span
                        className={
                          item.delta_trend_score >= 0
                            ? "fw-bold text-success"
                            : "fw-bold text-danger"
                        }
                      >
                        {item.delta_trend_score >= 0 ? "+" : ""}
                        {formatNumber(item.delta_trend_score)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default Hashtags;