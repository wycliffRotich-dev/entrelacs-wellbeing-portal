import { useEffect, useRef, useState } from "react";

import { ApiError, type Api } from "../api/client";
import type { CheckIn, DraftInput } from "../api/types";
import { QUESTIONS, type Answers, type QuestionKey } from "./questions";

const EMPTY: Answers = { connectedness: null, support: null, workload: null };

function answersOf(checkIn: CheckIn | null): Answers {
  if (checkIn === null) return EMPTY;
  return {
    connectedness: checkIn.connectedness,
    support: checkIn.support,
    workload: checkIn.workload,
  };
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "network_error":
        return error.message;
      case "check_in_already_submitted":
        return "This check-in was already submitted and can no longer be changed.";
      case "incomplete_check_in":
        return "Answer all three questions before submitting.";
      case "validation_error":
      case "invalid_answer":
        return "One or more answers are not valid. Choose a value from 0 to 10.";
    }
  }
  return "Something went wrong. Your answers are still on this page, so you can try again.";
}

export function useCheckIn(api: Api) {
  const [phase, setPhase] = useState<"loading" | "failed" | "ready">("loading");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [draft, setDraft] = useState<CheckIn | null>(null);
  const [latest, setLatest] = useState<CheckIn | null>(null);
  const [starting, setStarting] = useState(false);
  const [answers, setAnswers] = useState<Answers>(EMPTY);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<"save" | "submit" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [missing, setMissing] = useState<QuestionKey[]>([]);
  const inFlight = useRef(false);

  async function load(): Promise<void> {
    setPhase("loading");
    try {
      const current = await api.currentCheckIns();
      setDraft(current.draft);
      setLatest(current.latest_submitted);
      setAnswers(answersOf(current.draft));
      setDirty(false);
      setStarting(false);
      setMissing([]);
      setPhase("ready");
    } catch (e) {
      setLoadError(
        e instanceof ApiError && e.status === 0
          ? e.message
          : "We could not load your check-in. Please try again.",
      );
      setPhase("failed");
    }
  }

  useEffect(() => {
    void load();
  }, [api]);

  function choose(key: QuestionKey, value: number): void {
    setAnswers((a) => ({ ...a, [key]: value }));
    setDirty(true);
    setMissing((m) => m.filter((k) => k !== key));
    setError(null);
    setNotice(null);
  }

  async function persist(): Promise<CheckIn> {
    const input: DraftInput = {};
    for (const q of QUESTIONS) {
      const value = answers[q.key];
      if (value !== null) input[q.key] = value;
    }
    const saved = await api.saveDraft(input);
    setDraft(saved);
    setDirty(false);
    return saved;
  }

  async function fail(e: unknown): Promise<void> {
    setError(errorMessage(e));
    if (e instanceof ApiError && e.code === "check_in_already_submitted") await load();
  }

  async function save(): Promise<void> {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy("save");
    setError(null);
    setNotice(null);
    try {
      await persist();
      setNotice("Draft saved.");
    } catch (e) {
      await fail(e);
    } finally {
      inFlight.current = false;
      setBusy(null);
    }
  }

  async function submit(): Promise<void> {
    if (inFlight.current) return;
    const unanswered = QUESTIONS.filter((q) => answers[q.key] === null).map((q) => q.key);
    if (unanswered.length > 0) {
      setMissing(unanswered);
      setError("Answer all three questions before submitting.");
      return;
    }
    inFlight.current = true;
    setBusy("submit");
    setError(null);
    setNotice(null);
    try {
      const saved = dirty || draft === null ? await persist() : draft;
      const submitted = await api.submitCheckIn(saved.id);
      setLatest(submitted);
      setDraft(null);
      setAnswers(EMPTY);
      setDirty(false);
      setStarting(false);
    } catch (e) {
      await fail(e);
    } finally {
      inFlight.current = false;
      setBusy(null);
    }
  }

  function startNew(): void {
    setStarting(true);
    setAnswers(EMPTY);
    setDirty(false);
    setError(null);
    setNotice(null);
  }

  return {
    phase,
    loadError,
    draft,
    latest,
    starting,
    answers,
    dirty,
    busy,
    error,
    notice,
    missing,
    choose,
    save,
    submit,
    startNew,
    reload: load,
  };
}

export type CheckInState = ReturnType<typeof useCheckIn>;
