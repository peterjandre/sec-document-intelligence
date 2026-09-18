"use client";

import { useEffect, useMemo, useState } from "react";
import { displayAnswer, getHealth, isAnswerWarning, runQuery, type QueryResponse } from "../lib/api";
import styles from "./page.module.css";

const SAMPLE_QUESTIONS = [
  "How does Apple describe risks from concentrating manufacturing in a limited number of locations?",
  "What does NVIDIA disclose about export controls?",
  "How does Netflix describe content costs?",
  "Compare Apple and Amazon comments on competition.",
];

const MAX_QUESTION_CHARS = 1000;

function ExcerptText({ excerpt }: { excerpt: string }) {
  const divider = excerpt.indexOf("\n\n");
  if (divider === -1) {
    return <p className={styles.excerpt}>{excerpt}</p>;
  }
  return (
    <>
      <p className={styles.excerptHeading}>{excerpt.slice(0, divider)}</p>
      <p className={styles.excerpt}>{excerpt.slice(divider + 2)}</p>
    </>
  );
}

const ISSUERS = [
  { ticker: "AAPL", name: "Apple" },
  { ticker: "AMZN", name: "Amazon" },
  { ticker: "GOOG", name: "Alphabet" },
  { ticker: "META", name: "Meta" },
  { ticker: "NFLX", name: "Netflix" },
  { ticker: "NVDA", name: "NVIDIA" },
];

const STACK = [
  { name: "Next.js", detail: "App Router UI on Vercel" },
  { name: "FastAPI", detail: "Query and ingest orchestration" },
  { name: "C# / .NET", detail: "Regex extraction over 10-K HTML" },
  { name: "Python", detail: "Chunking, ticker routing, RAG pipeline" },
  { name: "OpenAI", detail: "text-embedding-3-small and gpt-4.1-nano" },
  { name: "Supabase", detail: "Postgres, pgvector, object storage" },
];

export default function HomePage() {
  const [question, setQuestion] = useState("");
  const [filingYear, setFilingYear] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">(
    "checking"
  );

  const canSubmit = useMemo(() => question.trim().length > 4, [question]);
  const nearLimit = question.length >= MAX_QUESTION_CHARS * 0.9;

  const ask = async (nextQuestion = question) => {
    const trimmed = nextQuestion.slice(0, MAX_QUESTION_CHARS).trim();
    if (trimmed.length < 5) return;
    try {
      setLoading(true);
      setError(null);
      const year = Number(filingYear);
      const data = await runQuery(
        trimmed,
        filingYear.trim() !== "" && (year === 2024 || year === 2025)
          ? { filingYear: year }
          : undefined
      );
      setResult(data);
    } catch (err) {
      setError(
        apiStatus === "offline"
          ? "The API is offline. Start the FastAPI server and try again."
          : err instanceof Error
            ? err.message
            : "Unexpected query error"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    getHealth()
      .then(() => setApiStatus("online"))
      .catch(() => setApiStatus("offline"));
  }, []);

  return (
    <>
      <a className={styles.skip} href="#ask">
        Skip to question
      </a>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <a className={styles.brand} href="#top">
            <span className={styles.brandMark} aria-hidden="true" />
            10-K Intelligence
          </a>
          <nav className={styles.nav} aria-label="Page">
            <a href="#ask">Ask a filing</a>
            <a href="#about">About This Project</a>
          </nav>
          <p className={styles.status} aria-live="polite">
            <span
              className={`${styles.statusDot} ${
                apiStatus === "online"
                  ? styles.statusOnline
                  : apiStatus === "offline"
                    ? styles.statusOffline
                    : styles.statusChecking
              }`}
            />
            {apiStatus === "checking"
              ? "Checking API"
              : apiStatus === "online"
                ? "API online"
                : "API offline"}
          </p>
        </div>
      </header>

      <main id="top">
        <section className={styles.hero} aria-labelledby="hero-title">
          <p className={styles.kicker}>Portfolio project · grounded retrieval</p>
          <h1 id="hero-title" className={styles.heroTitle}>
            Ask a 10-K. Read the evidence it came from.
          </h1>
          <p className={styles.heroLead}>
            A research-style Q&amp;A workspace over recent Form 10-K filings from
            six large issuers. Answers are generated only after similarity search
            finds supporting excerpts — then those excerpts stay on the page as
            citations.
          </p>
          <ul className={styles.issuerRow} aria-label="Indexed issuers">
            {ISSUERS.map((issuer) => (
              <li key={issuer.ticker}>
                <span className={styles.ticker}>{issuer.ticker}</span>
                <span>{issuer.name}</span>
              </li>
            ))}
          </ul>
        </section>

        <section id="ask" className={styles.ask} aria-labelledby="ask-title">
          <div className={styles.askIntro}>
            <h2 id="ask-title">Ask a filing</h2>
            <p>
              Name a company to route retrieval to that issuer, or ask a
              comparison. Optional year filter limits the search to a fiscal
              year.
            </p>
          </div>

          <form
            className={styles.panel}
            onSubmit={(event) => {
              event.preventDefault();
              void ask();
            }}
          >
            <label className={styles.srOnly} htmlFor="question">
              Question
            </label>
            <textarea
              id="question"
              className={styles.textarea}
              placeholder="What does Apple disclose about supplier concentration?"
              maxLength={MAX_QUESTION_CHARS}
              value={question}
              aria-describedby="question-count"
              onChange={(event) =>
                setQuestion(event.target.value.slice(0, MAX_QUESTION_CHARS))
              }
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                  event.preventDefault();
                  void ask();
                }
              }}
            />
            <p
              id="question-count"
              className={`${styles.charCount} ${nearLimit ? styles.charCountWarn : ""}`}
              aria-live="polite"
            >
              {question.length} / {MAX_QUESTION_CHARS}
            </p>
            <div className={styles.controls}>
              <label className={styles.yearLabel}>
                Filing year
                <select
                  className={styles.yearSelect}
                  value={filingYear}
                  onChange={(event) => setFilingYear(event.target.value)}
                >
                  <option value="">All years</option>
                  <option value="2024">2024</option>
                  <option value="2025">2025</option>
                </select>
              </label>
              <button
                className={styles.submit}
                type="submit"
                disabled={!canSubmit || loading}
              >
                {loading ? "Searching filings…" : "Ask"}
              </button>
            </div>
            <p className={styles.hint}>Press ⌘ Enter or Ctrl+Enter to submit.</p>
            <div className={styles.samples}>
              <p>Try a question</p>
              <ul>
                {SAMPLE_QUESTIONS.map((sample) => (
                  <li key={sample}>
                    <button
                      type="button"
                      className={styles.sample}
                      onClick={() => {
                        setQuestion(sample.slice(0, MAX_QUESTION_CHARS));
                        void ask(sample);
                      }}
                    >
                      {sample}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </form>

          {error ? (
            <p className={styles.error} role="alert">
              {error}
            </p>
          ) : null}

          {result ? (
            <section className={styles.results} aria-live="polite">
              <p className={styles.route}>
                {result.routed_tickers && result.routed_tickers.length > 0 ? (
                  <>
                    Routed to{" "}
                    {result.routed_tickers.map((ticker) => (
                      <span key={ticker} className={styles.routePill}>
                        {ticker}
                      </span>
                    ))}
                  </>
                ) : (
                  "No company named — searching all indexed issuers."
                )}
              </p>
              <article className={styles.answerCard}>
                <h3>Answer</h3>
                <p className={isAnswerWarning(result.answer) ? styles.answerWarn : styles.answer}>
                  {displayAnswer(result.answer)}
                </p>
              </article>
              <div className={styles.citationHeader}>
                <h3>Source excerpts</h3>
                <p>Retrieved chunks, not model-invented sources.</p>
              </div>
              <ol className={styles.citations}>
                {result.citations.map((citation, index) => (
                  <li
                    key={`${citation.document_id}-${index}`}
                    className={styles.citationCard}
                  >
                    <div className={styles.citationMeta}>
                      <span className={styles.citeIndex}>[{index + 1}]</span>
                      <strong>{citation.document_id}</strong>
                      <span className={styles.citationSection}>
                        {citation.section}
                      </span>
                      {citation.similarity > 0 ? (
                        <span className={styles.similarity}>
                          {(citation.similarity * 100).toFixed(0)}% match
                        </span>
                      ) : null}
                    </div>
                    <ExcerptText excerpt={citation.excerpt} />
                  </li>
                ))}
              </ol>
            </section>
          ) : (
            <p className={styles.empty}>
              Answers appear here with numbered excerpts you can check against
              the filing text.
            </p>
          )}
        </section>

        <section id="about" className={styles.about} aria-labelledby="about-title">
          <p className={styles.kicker}>Architecture and constraints</p>
          <h2 id="about-title">About This Project</h2>
          <p className={styles.aboutLead}>
          A document intelligence pipeline for SEC filings that combines deterministic parsing, regex-based document understanding, and retrieval-augmented generation for explainable financial document search.
          </p>

          <ol className={styles.pipeline}>
            <li>
              <span>01</span>
              <h3>Extract</h3>
              <p>
                A C# regex CLI reads filing HTML and emits structured JSON
                (sections and fields) for each 10-K.
              </p>
            </li>
            <li>
              <span>02</span>
              <h3>Index</h3>
              <p>
                Python chunks those sections, embeds them with OpenAI, and
                stores vectors in Supabase pgvector.
              </p>
            </li>
            <li>
              <span>03</span>
              <h3>Retrieve</h3>
              <p>
                FastAPI embeds the question, routes by ticker when a company is
                named, and keeps only chunks above a similarity threshold.
              </p>
            </li>
            <li>
              <span>04</span>
              <h3>Answer</h3>
              <p>
                OpenAI <code>gpt-4.1-nano</code> sees numbered excerpts and must
                cite <code>[n]</code>. Weak retrieval returns “no evidence” — the
                model is not asked to guess.
              </p>
            </li>
          </ol>

          <div className={styles.aboutGrid}>
            <div>
              <h3>What is indexed</h3>
              <p>
                Two recent Form 10-Ks each for Apple, Amazon, Alphabet, Meta,
                Netflix, and NVIDIA. Ticker aliases in the question (for
                example “Apple” or “Alphabet”) filter retrieval to that issuer.
                Comparisons keep both companies in the search set.
              </p>
              <h3>Guardrails that matter for 10-Ks</h3>
              <ul className={styles.guardrails}>
                <li>No numbers that are not in the retrieved excerpt.</li>
                <li>Prefer quoting figures over paraphrasing them.</li>
                <li>
                  Never mix companies unless the question asks for a comparison.
                </li>
                <li>
                  Citations on this page are the retrieved chunks, not sources
                  invented by the model.
                </li>
              </ul>
            </div>
            <aside className={styles.stack} aria-label="Technology used">
              <h3>Technology used</h3>
              <dl>
                {STACK.map((item) => (
                  <div key={item.name}>
                    <dt>{item.name}</dt>
                    <dd>{item.detail}</dd>
                  </div>
                ))}
              </dl>
            </aside>
          </div>

          <p className={styles.disclaimer}>
            This demo is for portfolio and research illustration. It is not
            investment advice, and it does not cover the full EDGAR corpus.
          </p>
        </section>
      </main>
    </>
  );
}
