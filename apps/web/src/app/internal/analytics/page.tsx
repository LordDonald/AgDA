"use client";

import {
  FormEvent,
  useState,
} from "react";

import styles from "./page.module.css";


type Overview = {
  total_questions: number;
  answered_count: number;
  clarification_count: number;
  reframe_count: number;
  unsupported_count: number;
  follow_up_count: number;
  follow_up_rate_pct: number | null;
  visualization_count: number;
  avg_processing_ms: number | null;
  p95_processing_ms: number | null;
  feedback_count: number;
  helpful_count: number;
  not_helpful_count: number;
  helpful_rate_pct: number | null;
};


type DailyUsage = {
  usage_date: string;
  total_questions: number;
  answered_count: number;
  clarification_count: number;
  reframe_count: number;
  unsupported_count: number;
  follow_up_count: number;
  follow_up_rate_pct: number | null;
  visualization_count: number;
  avg_processing_ms: number | null;
  p95_processing_ms: number | null;
};


type MetricUsage = {
  metric_id: string;
  question_count: number;
  follow_up_count: number;
  avg_processing_ms: number | null;
  p95_processing_ms: number | null;
  feedback_count: number;
  helpful_count: number;
  not_helpful_count: number;
  helpful_rate_pct: number | null;
};


type StatusSummary = {
  status: string;
  question_count: number;
  share_pct: number | null;
};


type FeedbackReason = {
  reason_code: string;
  feedback_count: number;
  share_pct: number | null;
};


type DashboardData = {
  overview: Overview;
  daily: DailyUsage[];
  metrics: MetricUsage[];
  statuses: StatusSummary[];
  feedbackReasons: FeedbackReason[];
};


async function loadResource(
  resource: string,
  token: string
) {

  const response =
    await fetch(
      (
        "/api/internal/analytics" +
        `?resource=${encodeURIComponent(
          resource
        )}`
      ),
      {
        headers: {
          "X-AgDA-Dashboard-Token":
            token,
        },

        cache:
          "no-store",
      }
    );


  const payload =
    await response.json();


  if (!response.ok) {

    throw new Error(
      typeof payload.detail
        === "string"
          ? payload.detail
          : (
              "Could not load internal " +
              "analytics."
            )
    );

  }


  return payload;
}


function formatPercent(
  value: number | null
) {

  if (value === null) {
    return "?";
  }

  return `${value.toFixed(1)}%`;
}


function formatMs(
  value: number | null
) {

  if (value === null) {
    return "?";
  }

  return `${value.toFixed(0)} ms`;
}


export default function InternalAnalyticsPage() {

  const [
    token,
    setToken,
  ] = useState("");

  const [
    data,
    setData,
  ] = useState<
    DashboardData | null
  >(null);

  const [
    loading,
    setLoading,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<
    string | null
  >(null);


  async function loadDashboard(
    event?: FormEvent<
      HTMLFormElement
    >
  ) {

    event?.preventDefault();


    const cleanToken =
      token.trim();


    if (
      !cleanToken
      ||
      loading
    ) {
      return;
    }


    setLoading(true);
    setError(null);


    try {

      const [
        overview,
        daily,
        metrics,
        statuses,
        feedbackReasons,
      ] = await Promise.all([
        loadResource(
          "overview",
          cleanToken
        ),

        loadResource(
          "daily",
          cleanToken
        ),

        loadResource(
          "metrics",
          cleanToken
        ),

        loadResource(
          "statuses",
          cleanToken
        ),

        loadResource(
          "feedback-reasons",
          cleanToken
        ),
      ]);


      setData({
        overview,
        daily,
        metrics,
        statuses,
        feedbackReasons,
      });

    } catch (
      loadError
    ) {

      setData(null);

      setError(
        loadError instanceof Error
          ? loadError.message
          : (
              "Could not load internal " +
              "analytics."
            )
      );

    } finally {

      setLoading(false);

    }
  }


  return (
    <main className={styles.page}>

      <header className={styles.header}>

        <div>

          <div className={styles.eyebrow}>
            AgDA internal
          </div>

          <h1>
            Product analytics
          </h1>

          <p>
            Privacy-safe usage,
            performance and feedback
            reporting.
          </p>

        </div>

      </header>


      {!data && (

        <section
          className={styles.loginCard}
        >

          <h2>
            Internal access
          </h2>

          <p>
            Enter the internal dashboard
            token to load analytics.
          </p>


          <form
            onSubmit={
              loadDashboard
            }
          >

            <input
              type="password"
              value={token}
              onChange={
                (
                  event
                ) =>
                  setToken(
                    event.target.value
                  )
              }
              placeholder={
                "Internal dashboard token"
              }
              autoComplete="off"
            />

            <button
              type="submit"
              disabled={
                loading
                ||
                !token.trim()
              }
            >
              {loading
                ? "Loading..."
                : "Open dashboard"}
            </button>

          </form>


          {error && (

            <div
              className={styles.error}
              role="alert"
            >
              {error}
            </div>

          )}

        </section>

      )}


      {data && (

        <>

          <div className={styles.toolbar}>

            <span>
              Internal analytics
            </span>

            <button
              type="button"
              onClick={() => {
                void loadDashboard();
              }}
              disabled={
                loading
              }
            >
              {loading
                ? "Refreshing..."
                : "Refresh"}
            </button>

          </div>


          <section
            className={styles.kpiGrid}
          >

            <div className={styles.kpi}>
              <span>Total questions</span>
              <strong>
                {
                  data
                  .overview
                  .total_questions
                }
              </strong>
            </div>


            <div className={styles.kpi}>
              <span>Answered</span>
              <strong>
                {
                  data
                  .overview
                  .answered_count
                }
              </strong>
            </div>


            <div className={styles.kpi}>
              <span>Follow-up rate</span>
              <strong>
                {formatPercent(
                  data
                    .overview
                    .follow_up_rate_pct
                )}
              </strong>
            </div>


            <div className={styles.kpi}>
              <span>Helpful rate</span>
              <strong>
                {formatPercent(
                  data
                    .overview
                    .helpful_rate_pct
                )}
              </strong>
              <small>
                Among submitted feedback
              </small>
            </div>


            <div className={styles.kpi}>
              <span>Average latency</span>
              <strong>
                {formatMs(
                  data
                    .overview
                    .avg_processing_ms
                )}
              </strong>
            </div>


            <div className={styles.kpi}>
              <span>P95 latency</span>
              <strong>
                {formatMs(
                  data
                    .overview
                    .p95_processing_ms
                )}
              </strong>
            </div>


            <div className={styles.kpi}>
              <span>Feedback responses</span>
              <strong>
                {
                  data
                  .overview
                  .feedback_count
                }
              </strong>
            </div>


            <div className={styles.kpi}>
              <span>Visualizations</span>
              <strong>
                {
                  data
                  .overview
                  .visualization_count
                }
              </strong>
            </div>

          </section>


          <section className={styles.card}>

            <h2>
              Daily usage
            </h2>

            <div className={styles.tableWrap}>

              <table>

                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Questions</th>
                    <th>Answered</th>
                    <th>Follow-ups</th>
                    <th>Follow-up rate</th>
                    <th>Avg latency</th>
                    <th>P95 latency</th>
                  </tr>
                </thead>

                <tbody>

                  {
                    data.daily.map(
                      (
                        row
                      ) => (

                        <tr
                          key={
                            row.usage_date
                          }
                        >
                          <td>
                            {row.usage_date}
                          </td>
                          <td>
                            {
                              row
                              .total_questions
                            }
                          </td>
                          <td>
                            {
                              row
                              .answered_count
                            }
                          </td>
                          <td>
                            {
                              row
                              .follow_up_count
                            }
                          </td>
                          <td>
                            {formatPercent(
                              row
                                .follow_up_rate_pct
                            )}
                          </td>
                          <td>
                            {formatMs(
                              row
                                .avg_processing_ms
                            )}
                          </td>
                          <td>
                            {formatMs(
                              row
                                .p95_processing_ms
                            )}
                          </td>
                        </tr>

                      )
                    )
                  }

                </tbody>

              </table>

            </div>

          </section>


          <section className={styles.card}>

            <h2>
              Metric usage
            </h2>

            <div className={styles.tableWrap}>

              <table>

                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Questions</th>
                    <th>Follow-ups</th>
                    <th>Feedback</th>
                    <th>Helpful</th>
                    <th>Not helpful</th>
                    <th>Helpful rate</th>
                  </tr>
                </thead>

                <tbody>

                  {
                    data.metrics.map(
                      (
                        row
                      ) => (

                        <tr
                          key={
                            row.metric_id
                          }
                        >
                          <td>
                            {row.metric_id}
                          </td>
                          <td>
                            {
                              row
                              .question_count
                            }
                          </td>
                          <td>
                            {
                              row
                              .follow_up_count
                            }
                          </td>
                          <td>
                            {
                              row
                              .feedback_count
                            }
                          </td>
                          <td>
                            {
                              row
                              .helpful_count
                            }
                          </td>
                          <td>
                            {
                              row
                              .not_helpful_count
                            }
                          </td>
                          <td>
                            {formatPercent(
                              row
                                .helpful_rate_pct
                            )}
                          </td>
                        </tr>

                      )
                    )
                  }

                </tbody>

              </table>

            </div>

          </section>


          <div className={styles.twoColumn}>

            <section className={styles.card}>

              <h2>
                Response statuses
              </h2>

              <div
                className={styles.list}
              >

                {
                  data.statuses.map(
                    (
                      row
                    ) => (

                      <div
                        className={
                          styles.listRow
                        }
                        key={
                          row.status
                        }
                      >
                        <span>
                          {
                            row.status
                            .replaceAll(
                              "_",
                              " "
                            )
                          }
                        </span>

                        <strong>
                          {
                            row
                            .question_count
                          }
                          {" ? "}
                          {formatPercent(
                            row.share_pct
                          )}
                        </strong>
                      </div>

                    )
                  )
                }

              </div>

            </section>


            <section className={styles.card}>

              <h2>
                Negative feedback reasons
              </h2>

              {
                data.feedbackReasons.length
                === 0
                  ? (

                    <p
                      className={
                        styles.empty
                      }
                    >
                      No negative feedback
                      reasons recorded.
                    </p>

                  )
                : (

                  <div
                    className={
                      styles.list
                    }
                  >

                    {
                      data
                      .feedbackReasons
                      .map(
                        (
                          row
                        ) => (

                          <div
                            className={
                              styles.listRow
                            }
                            key={
                              row.reason_code
                            }
                          >
                            <span>
                              {
                                row
                                .reason_code
                                .replaceAll(
                                  "_",
                                  " "
                                )
                              }
                            </span>

                            <strong>
                              {
                                row
                                .feedback_count
                              }
                              {" ? "}
                              {formatPercent(
                                row.share_pct
                              )}
                            </strong>
                          </div>

                        )
                      )
                    }

                  </div>

                )
              }

            </section>

          </div>

        </>

      )}

    </main>
  );
}
