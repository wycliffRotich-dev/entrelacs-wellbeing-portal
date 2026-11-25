import { useAuth } from "../auth";
import type { Wellbeing } from "../api/types";
import { formatAverage, formatParticipation } from "./format";
import { useWellbeing } from "./useWellbeing";

function Overview({ data }: { data: Wellbeing }) {
  return (
    <>
      <p className="hint">Reporting month: {data.reporting_month}</p>
      <dl className="metrics">
        <div className="metric">
          <dt>Average score</dt>
          <dd>{formatAverage(data)}</dd>
        </div>
        <div className="metric">
          <dt>Respondents</dt>
          <dd>{data.respondent_count}</dd>
        </div>
        <div className="metric">
          <dt>Eligible employees</dt>
          <dd>{data.eligible_count}</dd>
        </div>
        <div className="metric">
          <dt>Participation</dt>
          <dd>{formatParticipation(data)}</dd>
        </div>
      </dl>
      {data.respondent_count === 0 && data.eligible_count > 0 && (
        <p>No check-ins were submitted this month.</p>
      )}
    </>
  );
}

export function HrHome() {
  const { api } = useAuth();
  const { teamId, selectTeam, retry, teams, summary } = useWellbeing(api);

  function body() {
    if (summary.phase === "loading" || teams.phase === "loading") {
      return <p role="status">Loading dashboard…</p>;
    }
    if (summary.phase === "failed") {
      return (
        <div role="alert" className="alert">
          <p>{summary.message}</p>
          <button type="button" onClick={retry}>
            Try again
          </button>
        </div>
      );
    }
    return <Overview data={summary.data} />;
  }

  return (
    <>
      <h1>Organization wellbeing</h1>
      <div className="filter">
        <label htmlFor="team-filter">Team</label>
        <select
          id="team-filter"
          value={teamId ?? ""}
          onChange={(event) => selectTeam(event.target.value)}
        >
          <option value="">All teams</option>
          {teams.phase === "ready" &&
            teams.list.map((team) => (
              <option key={team.id} value={team.id}>
                {team.name}
              </option>
            ))}
        </select>
      </div>
      {teams.phase === "failed" && (
        <p className="hint">The team list could not be loaded. Showing the whole organization.</p>
      )}
      {body()}
    </>
  );
}
