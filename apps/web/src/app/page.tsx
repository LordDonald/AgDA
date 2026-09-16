"use client";

import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";


type Evidence = {
  evidence_grade: string;
  records: number;
  households: number | null;
  clusters: number | null;
  denominator_households: number | null;
  minimum_evidence_threshold: number;
  claim_type: string | null;
  methodological_caution: string | null;
};


type Visualization = {
  recommended: boolean;
  visual_type: string | null;
  title: string | null;
  dimension: string | null;
  metric_id: string | null;
  unit: string | null;
  data: Record<string, unknown>[] | null;
};


type Clarification = {
  clarification_required: boolean;
  prompt: string;
  options: string[];

  resolved_entities: Record<
    string,
    string[]
  >;

  candidate_metrics: string[];
};


type Reframe = {
  original_request_type: string;
  reason: string;
  supported_alternative: string | null;
};


type AgDAAnswer = {
  status: string;

  question: string;

  conversation_id: string | null;

  answer_text: string;

  result:
    | Record<string, unknown>
    | Record<string, unknown>[]
    | null;

  evidence: Evidence | null;

  visualization: Visualization | null;

  clarification: Clarification | null;

  reframe: Reframe | null;

  warnings: string[];

  data_version: string;

  metric_version: string | null;
};


type ConversationTurn = {
  id: string;
  question: string;
  answer: AgDAAnswer;
};


const exampleQuestions = [
  "What crops do people farm most in Kaduna?",
  "How risky is flooding in the North West?",
  "Which crops have the highest yields in Nigeria?",
  "Is food security better after harvest?",
];


function formatValue(
  value: unknown,
  unit: string | null
) {
  if (
    typeof value !== "number"
  ) {
    return String(
      value ?? ""
    );
  }


  if (unit === "proportion") {
    return `${(
      value * 100
    ).toFixed(1)}%`;
  }


  if (unit === "%") {
    return `${value.toFixed(1)}%`;
  }


  if (unit === "kg/ha") {
    return `${value.toLocaleString(
      undefined,
      {
        maximumFractionDigits: 1,
      }
    )} kg/ha`;
  }


  if (unit === "ha") {
    return `${value.toFixed(3)} ha`;
  }


  return value.toLocaleString(
    undefined,
    {
      maximumFractionDigits: 2,
    }
  );
}


function buildClarificationQuestion(
  answer: AgDAAnswer,
  option: string
): string | null {

  const crop = (
    answer
    .clarification
    ?.resolved_entities
    ?.crop?.[0]
  );


  if (!crop) {
    return null;
  }


  switch (option) {

    case "observed yield":

      return (
        `Which states have the highest ` +
        `yields for ${crop}?`
      );


    case "how commonly the crop is grown":

      return (
        `Which states have the highest ` +
        `grower share for ${crop}?`
      );


    case "seller participation":

      return (
        `Which states have the highest ` +
        `seller participation for ${crop}?`
      );


    case "commercialization share":

      return (
        `Which states have the highest ` +
        `commercialization share for ${crop}?`
      );


    default:

      return null;
  }
}


function RankedResults({
  answer,
}: {
  answer: AgDAAnswer;
}) {

  if (
    !Array.isArray(
      answer.result
    )
    ||
    answer.result.length === 0
  ) {
    return null;
  }


  const dimension = (
    answer
    .visualization
    ?.dimension
  );


  const unit = (
    answer
    .visualization
    ?.unit
    ?? null
  );


  if (!dimension) {
    return null;
  }


  const values = (
    answer.result.map(
      (row) =>
        typeof row.value
        === "number"
          ? row.value
          : 0
    )
  );


  const maxValue = Math.max(
    ...values,
    0
  );


  return (
    <div className="ranking">

      {answer.result.map(
        (
          row,
          index
        ) => {

          const value = (
            typeof row.value
            === "number"
              ? row.value
              : 0
          );


          const label = String(
            row[
              dimension
            ]
            ?? "Unknown"
          );


          const width = (
            maxValue > 0
              ? Math.max(
                  (
                    value
                    / maxValue
                  )
                  * 100,
                  4
                )
              : 0
          );


          return (
            <div
              className="rankingRow"
              key={
                `${label}-${index}`
              }
            >

              <div className="rankingHeader">

                <span className="rankingLabel">
                  {label}
                </span>

                <span className="rankingValue">
                  {formatValue(
                    value,
                    unit
                  )}
                </span>

              </div>


              <div className="barTrack">

                <div
                  className="barFill"
                  style={{
                    width:
                      `${width}%`,
                  }}
                />

              </div>


              <div className="rankingMeta">

                {typeof row.records
                  === "number" && (
                  <span>
                    {row.records
                      .toLocaleString()}{" "}
                    records
                  </span>
                )}


                {typeof row
                  .evidence_grade
                  === "string" && (
                  <span>
                    {
                      row
                      .evidence_grade
                    }{" "}
                    evidence
                  </span>
                )}

              </div>

            </div>
          );
        }
      )}

    </div>
  );
}


function AnswerCard({
  answer,
  loading,
  onFollowUp,
}: {
  answer: AgDAAnswer;
  loading: boolean;
  onFollowUp:
    (
      question: string
    ) => void;
}) {

  return (
    <section className="responseCard">

      <div className="responseTop">

        <div>

          <div className="responseLabel">
            AgDA answer
          </div>


          <h2>

            {answer.status
              === "answered"
                ? "What the data shows"

              : answer.status
                ===
                "needs_clarification"
                  ? "A little more detail"

              : answer.status
                ===
                "reframe_required"
                  ? "A safer comparison"

              : "Data limitation"}

          </h2>

        </div>


        <span
          className={
            `answerStatus ` +
            `${answer.status}`
          }
        >
          {answer.status
            .replaceAll(
              "_",
              " "
            )}
        </span>

      </div>


      <p className="answerText">
        {answer.answer_text}
      </p>


      {answer.status
        === "answered" && (

        <RankedResults
          answer={answer}
        />

      )}


      {answer.evidence && (

        <div className="evidencePanel">

          <div className="evidenceBadge">

            {
              answer
              .evidence
              .evidence_grade
            }{" "}
            evidence

          </div>


          <div className="evidenceStats">

            <span>
              {answer
                .evidence
                .records
                .toLocaleString()}{" "}
              supporting records
            </span>


            {answer
              .evidence
              .households
              !== null && (

              <span>
                {answer
                  .evidence
                  .households
                  .toLocaleString()}{" "}
                households
              </span>

            )}


            {answer
              .evidence
              .clusters
              !== null && (

              <span>
                {answer
                  .evidence
                  .clusters
                  .toLocaleString()}{" "}
                sampled communities
              </span>

            )}

          </div>

        </div>
      )}


      {answer.clarification
        &&
        answer
        .clarification
        .options
        .length > 0 && (

        <div className="followUps">

          <div className="sectionLabel">
            Choose what you mean
          </div>


          <div className="exampleButtons">

            {answer
              .clarification
              .options
              .map(
                (option) => {

                  const followUpQuestion = (
                    buildClarificationQuestion(
                      answer,
                      option
                    )
                  );


                  return (
                    <button
                      className="optionChip"
                      key={option}
                      type="button"

                      disabled={
                        loading
                        ||
                        !followUpQuestion
                      }

                      onClick={() => {

                        if (
                          followUpQuestion
                        ) {

                          onFollowUp(
                            followUpQuestion
                          );

                        }

                      }}
                    >
                      {option}
                    </button>
                  );
                }
              )}

          </div>

        </div>
      )}


      {answer.warnings.length
        > 0 && (

        <details className="methodology">

          <summary>
            Methodological note
          </summary>


          {answer.warnings.map(
            (warning) => (

              <p key={warning}>
                {warning}
              </p>

            )
          )}

        </details>
      )}


      <div className="provenance">

        <span>
          Data:{" "}
          {answer.data_version}
        </span>


        {answer.metric_version && (

          <span>
            Metric:{" "}
            {answer.metric_version}
          </span>

        )}

      </div>

    </section>
  );
}


export default function Home() {

  const [
    question,
    setQuestion,
  ] = useState("");

    const [
      pendingQuestion,
      setPendingQuestion,
    ] = useState<string | null>(
      null
    );


  const [
    turns,
    setTurns,
  ] = useState<
    ConversationTurn[]
  >([]);


  const [
    conversationId,
    setConversationId,
  ] = useState<
    string | null
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


  const [
    backendReady,
    setBackendReady,
  ] = useState<
    boolean | null
  >(null);


  const conversationEndRef =
    useRef<HTMLDivElement | null>(
      null
    );

    async function checkBackendHealth() {

      setBackendReady(
        null
      );


      try {

        const response = (
          await fetch(
            "/api/health",
            {
              cache:
                "no-store",
            }
          )
        );


        const payload = (
          await response.json()
        );


        const ready = Boolean(
          response.ok
          &&
          payload.ready
        );


        setBackendReady(
          ready
        );


        return ready;

      } catch {

        setBackendReady(
          false
        );


        return false;

      }
    }


  useEffect(() => {

    let cancelled = false;


    async function loadInitialHealth() {
        
        try {
            
            const response = (
                await fetch(
                  "/api/health",
                  {
                    cache:
                      "no-store",
                  }
                )
              );


              const payload = (
                await response.json()
              );


              if (!cancelled) {

                setBackendReady(
                  Boolean(
                    response.ok
                    &&
                    payload.ready
                  )
                );
              
              }
        
        } catch {

          if (!cancelled) {

            setBackendReady(
              false
            );

          }

        }
      }


      void loadInitialHealth();


      return () => {

        cancelled = true;

      };

    }, []);


  useEffect(() => {

    if (
      turns.length > 0
      ||
      pendingQuestion
    ) {

      conversationEndRef
        .current
        ?.scrollIntoView({
          behavior:
            "smooth",

          block:
            "end",
        });

    }

  }, [
    turns.length,
    pendingQuestion,
  ]);


  async function submitQuestion(
    submittedQuestion: string
  ) {

    const cleanQuestion = (
      submittedQuestion
      .trim()
    );


    if (
      !cleanQuestion
      ||
      loading
    ) {
      return;
    }

    if (
      backendReady === false
    ) {

      setError(
        "The AgDA data service is currently offline. " +
        "Reconnect to the data service before trying again."
      );


      setQuestion(
        cleanQuestion
      );


      return;
    }


    setLoading(true);

    setError(null);

    setPendingQuestion(
      cleanQuestion
    );

    setQuestion("");


    try {

      const response = (
        await fetch(
          "/api/questions",
          {
            method:
              "POST",

            headers: {
              "Content-Type":
                "application/json",
            },

            body: JSON.stringify({
              question:
                cleanQuestion,

              conversation_id:
                conversationId,

              max_rank_items:
                5,

              include_visualization:
                true,

              locale:
                "en-NG",
            }),
          }
        )
      );


      const payload = (
        await response.json()
      );


    if (!response.ok) {
        
        if (
            response.status >= 500
            ||
            payload.status
            === "system_error"
          ) {

            setBackendReady(
              false
            );

          }


          throw new Error(
            typeof payload.detail
              === "string"
                ? payload.detail

              : payload.message
                ?? payload.answer_text
                ?? (
                  "AgDA could not " +
                  "complete the request."
                )
          );

        }


      const answer = (
        payload as AgDAAnswer
      );


      if (
        answer
        .conversation_id
      ) {

        setConversationId(
          answer
          .conversation_id
        );

      }


      setTurns(
        (
          previousTurns
        ) => [
          ...previousTurns,

          {
            id:
              crypto
              .randomUUID(),

            question:
              cleanQuestion,

            answer:
              answer,
          },
        ]
      );


      setPendingQuestion(
          null
      );

    } catch (
      requestError
    ) {

      setError(
        requestError
          instanceof Error
            ? requestError.message
            : "Something went wrong."
      );
        
    
      setQuestion(
        cleanQuestion
      );


      setPendingQuestion(
        null
      );

    } finally {

      setLoading(false);

    }
  }


  function handleSubmit(
    event:
      FormEvent<
        HTMLFormElement
      >
  ) {

    event.preventDefault();

    submitQuestion(
      question
    );
  }

    function handleQuestionKeyDown(
      event:
        KeyboardEvent<
          HTMLTextAreaElement
        >
    ) {

      if (
        event.key === "Enter"
        &&
        !event.shiftKey
      ) {

        event.preventDefault();


        if (
          !loading
          &&
          question.trim()
        ) {

          submitQuestion(
            question
          );

        }

      }
    }
    
    function startNewConversation() {

      setConversationId(
        null
      );

      setTurns([]);

      setQuestion("");

      setPendingQuestion(
        null
      );

      setError(null);


      window.scrollTo({
        top: 0,
        behavior:
          "smooth",
      });
    }


  return (
    <main className="pageShell">

      <header className="siteHeader">

        <div className="brand">

          <div className="brandMark">
            A
          </div>


          <div>

            <div className="brandName">
              AgDA
            </div>

            <div className="brandTagline">
              Agricultural Data Assistant
            </div>

          </div>

        </div>


        <div className="headerActions">

          {turns.length > 0 && (

            <button
              className="newConversationButton"
              type="button"
              onClick={
                startNewConversation
              }
              disabled={
                loading
              }
            >
              New conversation
            </button>

          )}


          <div
            className={
              backendReady
                ? "statusBadge ready"

              : backendReady
                === false
                  ? "statusBadge offline"

              : "statusBadge"
            }
          >

            <span className="statusDot" />


            {backendReady === null
              ? "Checking data service"

              : backendReady
                ? "Wave 5 data ready"

              : "Data service offline"}

          </div>

        </div>

      </header>


      <section className="hero">

        <div className="eyebrow">
          Evidence-backed
          agricultural intelligence
        </div>


        <h1>
          Ask Nigeria&apos;s
          agricultural data.
        </h1>


        <p className="heroText">

          Explore crop production,
          commercialization,
          food security,
          agricultural information,
          prices and climate evidence
          from the validated
          Wave 5 survey.

        </p>


        <form
          className="questionForm"
          onSubmit={
            handleSubmit
          }
        >

          <textarea
            value={question}

            onChange={
              (
                event
              ) =>
                setQuestion(
                  event
                  .target
                  .value
                )
            }

            onKeyDown={
              handleQuestionKeyDown
            }

            placeholder={
              turns.length > 0
                ? (
                    "Ask a follow-up, " +
                    "for example: " +
                    "What about Kaduna?"
                  )
                : (
                    "Ask a question, " +
                    "for example: " +
                    "What crops do people " +
                    "farm most in Kaduna?"
                  )
            }

            rows={3}

            disabled={
              loading
            }
          />


          <div className="formFooter">

            <span className="formHint">

              {conversationId
                ? (
                    "AgDA will use context " +
                    "from this conversation."
                  )
                : (
                    "AgDA answers from " +
                    "validated survey " +
                    "evidence, not from " +
                    "invented statistics."
                  )}

            </span>


            <button
              type="submit"

              disabled={
                loading
                ||
                !question.trim()
                ||
                backendReady === false
              }
            >

              {loading
                ? "Analysing..."
                : "Ask AgDA"}

            </button>

          </div>

        </form>


        {turns.length === 0 && (

          <div className="examples">

            <span className="examplesLabel">
              Try asking
            </span>


            <div className="exampleButtons">

              {exampleQuestions.map(
                (example) => (

                  <button
                    className="exampleButton"

                    key={example}

                    type="button"

                    disabled={
                      loading
                      ||
                      backendReady === false  
                    }

                    onClick={() =>
                      submitQuestion(
                        example
                      )
                    }
                  >
                    {example}
                  </button>

                )
              )}

            </div>

          </div>

        )}

      </section>


      {error && (

          <section className="responseCard errorCard">

            <div className="responseLabel">
              Unable to answer
            </div>


            <h2 className="errorTitle">
              AgDA could not complete the request
            </h2>


            <p className="errorMessage">
                {error}
            </p>


            {backendReady === false && (

              <button
                type="button"
                className="retryButton"

                onClick={
                  async () => {

                    const ready = (
                      await checkBackendHealth()
                    );


                    if (ready) {

                      setError(
                        null
                      );

                    }

                  }
                }
              >
                Retry connection
              </button>

            )}

          </section>

        )}


      {(
        turns.length > 0 
        ||
        pendingQuestion
      ) && (

        <section className="conversationHistory">

          {turns.map(
            (
              turn
            ) => (

              <article
                className="conversationTurn"
                key={turn.id}
              >

                <div className="userBubble">

                  <div className="userLabel">
                    You
                  </div>

                  <p>
                    {turn.question}
                  </p>

                </div>


                <AnswerCard
                  answer={
                    turn.answer
                  }

                  loading={
                    loading
                  }

                  onFollowUp={
                    submitQuestion
                  }
                />

              </article>

            )
          )}

        {pendingQuestion && (

          <article
            className="
              conversationTurn
              pendingTurn
            "
          >

            <div className="userBubble">

              <div className="userLabel">
                You
              </div>

              <p>
                {pendingQuestion}
              </p>

            </div>


            <section
              className="
                responseCard
                loadingResponseCard
            "
            aria-live="polite"
          >

            <div className="responseLabel">
              AgDA
            </div>


            <div className="loadingAnswer">

                <span className="loadingSpinner" />

                <div>

                  <h2>
                    Analysing your question
                  </h2>

                  <p>
                    Checking the relevant
                    Wave 5 evidence and
                    analytical measures.
                  </p>

                </div>

              </div>

            </section>

          </article>

        )}


          <div
            ref={
              conversationEndRef
            }
          />

        </section>

      )}


      <footer className="siteFooter">

        <p>
          AgDA provides descriptive
          survey evidence. It does not
          replace agronomic,
          financial or meteorological
          advice.
        </p>

      </footer>

    </main>
  );
}