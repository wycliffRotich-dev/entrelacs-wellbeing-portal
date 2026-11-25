import { useEffect, useState } from "react";

import { ApiError, type Api } from "../api/client";
import type { Team, Wellbeing } from "../api/types";

export type SummaryState =
  | { phase: "loading" }
  | { phase: "failed"; message: string }
  | { phase: "ready"; data: Wellbeing };

export type TeamsState =
  | { phase: "loading" }
  | { phase: "failed" }
  | { phase: "ready"; list: Team[] };

function loadMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 0) return error.message;
  return "We could not load the dashboard. Please try again.";
}

export function useWellbeing(api: Api) {
  const [teamId, setTeamId] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [teams, setTeams] = useState<TeamsState>({ phase: "loading" });
  const [summary, setSummary] = useState<SummaryState>({ phase: "loading" });

  useEffect(() => {
    let current = true;
    api.teams().then(
      (list) => {
        if (current) setTeams({ phase: "ready", list });
      },
      () => {
        if (current) setTeams({ phase: "failed" });
      },
    );
    return () => {
      current = false;
    };
  }, [api]);

  // Each selection or retry starts a new request. A reply for an older one is ignored.
  useEffect(() => {
    let current = true;
    setSummary({ phase: "loading" });
    api.wellbeing(teamId).then(
      (data) => {
        if (current) setSummary({ phase: "ready", data });
      },
      (error: unknown) => {
        if (current) setSummary({ phase: "failed", message: loadMessage(error) });
      },
    );
    return () => {
      current = false;
    };
  }, [api, teamId, attempt]);

  return {
    teamId,
    selectTeam: (value: string) => setTeamId(value === "" ? null : value),
    retry: () => setAttempt((n) => n + 1),
    teams,
    summary,
  };
}
