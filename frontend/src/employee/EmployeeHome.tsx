import type { ReactNode } from "react";

import type { CheckIn } from "../api/types";
import { useAuth } from "../auth";
import { QUESTIONS, SCALE } from "./questions";
import { useCheckIn, type CheckInState } from "./useCheckIn";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: "UTC" });
}

function SubmittedSummary({ checkIn, heading }: { checkIn: CheckIn; heading: string }) {
  return (
    <section className="card" aria-labelledby="summary-title">
      <h2 id="summary-title">{heading}</h2>
      {checkIn.score !== null && (
        <p className="score">
          Score: <strong>{checkIn.score.toFixed(1)}</strong> out of 100
        </p>
      )}
      <dl className="answers">
        {QUESTIONS.map((q) => (
          <div key={q.key}>
            <dt>{q.label}</dt>
            <dd>{checkIn[q.key] ?? "-"} / 10</dd>
          </div>
        ))}
      </dl>
      {checkIn.submitted_at !== null && (
        <p className="muted">
          Submitted {formatDate(checkIn.submitted_at)}. Submitted check-ins cannot be edited.
        </p>
      )}
    </section>
  );
}

function CheckInForm({ c, messages }: { c: CheckInState; messages: ReactNode }) {
  const busy = c.busy !== null;
  return (
    <form
      className="card"
      aria-label="Wellbeing check-in"
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void c.submit();
      }}
    >
      <p className="muted">Answer each question from 0 (least positive) to 10 (most positive).</p>
      {c.draft !== null && <p className="muted">Continuing your saved draft.</p>}
      {QUESTIONS.map((q) => {
        const hasError = c.missing.includes(q.key);
        const errorId = `${q.key}-error`;
        return (
          <fieldset key={q.key} className="question" aria-describedby={hasError ? errorId : undefined}>
            <legend>{q.label}</legend>
            <div className="scale">
              {SCALE.map((n) => (
                <label key={n} className="scale-option">
                  <input
                    type="radio"
                    name={q.key}
                    value={n}
                    checked={c.answers[q.key] === n}
                    onChange={() => c.choose(q.key, n)}
                  />
                  <span>{n}</span>
                </label>
              ))}
            </div>
            {hasError && (
              <p id={errorId} className="field-error">
                Choose an answer from 0 to 10.
              </p>
            )}
          </fieldset>
        );
      })}
      {messages}
      <div className="actions">
        <button
          type="button"
          className="secondary"
          disabled={!c.dirty || busy}
          onClick={() => void c.save()}
        >
          {c.busy === "save" ? "Saving…" : "Save draft"}
        </button>
        <button type="submit" disabled={busy}>
          {c.busy === "submit" ? "Submitting…" : "Submit check-in"}
        </button>
      </div>
    </form>
  );
}

function Ready({ c }: { c: CheckInState }) {
  const showForm = c.draft !== null || c.starting || c.latest === null;
  const messages = (
    <>
      {c.error !== null && (
        <p role="alert" className="alert">
          {c.error}
        </p>
      )}
      {c.notice !== null && (
        <p role="status" className="notice">
          {c.notice}
        </p>
      )}
    </>
  );
  return (
    <>
      {!showForm && messages}
      {showForm && c.latest === null && c.draft === null && (
        <p className="muted">You have not submitted a check-in yet.</p>
      )}
      {showForm && <CheckInForm c={c} messages={messages} />}
      {c.latest !== null && (
        <SubmittedSummary
          checkIn={c.latest}
          heading={showForm ? "Your previous check-in" : "Your latest result"}
        />
      )}
      {!showForm && (
        <button type="button" onClick={c.startNew}>
          Start a new check-in
        </button>
      )}
    </>
  );
}

export function EmployeeHome() {
  const { api } = useAuth();
  const c = useCheckIn(api);
  return (
    <div className="stack">
      <h1>Your check-in</h1>
      {c.phase === "loading" && <p role="status">Loading your check-in…</p>}
      {c.phase === "failed" && (
        <div role="alert" className="alert">
          <p>{c.loadError}</p>
          <button type="button" onClick={() => void c.reload()}>
            Try again
          </button>
        </div>
      )}
      {c.phase === "ready" && <Ready c={c} />}
    </div>
  );
}
