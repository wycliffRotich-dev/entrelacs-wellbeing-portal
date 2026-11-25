import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { Wellbeing } from "../api/types";
import { App } from "../App";
import { setToken } from "../session";
import { fakeFetch, json } from "../test/fakeFetch";

const HR = {
  id: "h1",
  email: "hr@northwind.example.test",
  role: "HR",
  organization_id: "o1",
  team_id: null,
};
const TEAMS = [
  { id: "t1", name: "Platform" },
  { id: "t2", name: "Ops" },
];
const ORG_URL = "GET /api/hr/wellbeing";
const TEAM_URL = "GET /api/hr/wellbeing?team_id=t1";

function summary(over: Partial<Wellbeing> = {}): Wellbeing {
  return {
    reporting_month: "2026-10",
    team_id: null,
    respondent_count: 8,
    eligible_count: 14,
    participation_rate: 57.1,
    average_score: 68.3,
    suppressed: false,
    ...over,
  };
}

type Routes = Parameters<typeof fakeFetch>[0];

function dashboard(extra: Routes) {
  return fakeFetch({
    "GET /api/auth/me": () => json(200, HR),
    "GET /api/hr/teams": () => json(200, TEAMS),
    ...extra,
  });
}

function open(fetchFn: typeof fetch) {
  setToken("test-token");
  render(<App fetchFn={fetchFn} />);
}

async function metric(label: string): Promise<string> {
  const term = await screen.findByText(label, { selector: "dt" });
  return term.nextElementSibling?.textContent ?? "";
}

describe("HR dashboard", () => {
  it("shows a loading state, then the organization overview for the reporting month", async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    open(
      dashboard({
        [ORG_URL]: async () => {
          await gate;
          return json(200, summary());
        },
      }),
    );

    expect(await screen.findByText("Loading dashboard…")).toBeInTheDocument();
    release();

    expect(await metric("Average score")).toBe("68.3");
    expect(await metric("Respondents")).toBe("8");
    expect(await metric("Eligible employees")).toBe("14");
    expect(await metric("Participation")).toBe("57.1%");
    expect(screen.getByText(/2026-10/)).toBeInTheDocument();
    expect(screen.queryByText("Loading dashboard…")).not.toBeInTheDocument();
  });

  it("offers every team in a labelled filter, defaulting to the whole organization", async () => {
    open(dashboard({ [ORG_URL]: () => json(200, summary()) }));
    await metric("Average score");

    const filter = screen.getByLabelText("Team");
    expect(filter).toHaveValue("");
    expect(screen.getByRole("option", { name: "All teams" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Platform" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Ops" })).toBeInTheDocument();
  });

  it("shows the selected team's numbers and goes back to the overview", async () => {
    const fetchFn = dashboard({
      [ORG_URL]: () => json(200, summary()),
      [TEAM_URL]: () =>
        json(200, summary({ team_id: "t1", respondent_count: 7, eligible_count: 7, participation_rate: 100, average_score: 71.4 })),
    });
    open(fetchFn);
    await metric("Average score");
    const user = userEvent.setup();

    await user.selectOptions(screen.getByLabelText("Team"), "Platform");
    await waitFor(async () => expect(await metric("Average score")).toBe("71.4"));
    expect(await metric("Participation")).toBe("100%");

    await user.selectOptions(screen.getByLabelText("Team"), "All teams");
    await waitFor(async () => expect(await metric("Average score")).toBe("68.3"));
  });

  it("withholds the average and says so when there are fewer than five respondents", async () => {
    open(
      dashboard({
        [ORG_URL]: () =>
          json(200, summary({ respondent_count: 3, eligible_count: 14, participation_rate: 21.4, average_score: null, suppressed: true })),
      }),
    );

    expect(await metric("Average score")).toBe("Insufficient responses");
    expect(await metric("Respondents")).toBe("3");
    expect(await metric("Participation")).toBe("21.4%");
  });

  it("says there are no eligible employees instead of a percentage when the denominator is zero", async () => {
    open(
      dashboard({
        [ORG_URL]: () => json(200, summary()),
        [TEAM_URL]: () =>
          json(200, summary({ team_id: "t1", respondent_count: 0, eligible_count: 0, participation_rate: null, average_score: null, suppressed: true })),
      }),
    );
    await metric("Average score");

    await userEvent.setup().selectOptions(screen.getByLabelText("Team"), "Platform");

    await waitFor(async () => expect(await metric("Participation")).toBe("No eligible employees"));
    expect(await metric("Average score")).toBe("Insufficient responses");
    expect(await metric("Respondents")).toBe("0");
  });

  it("shows an empty state when employees are eligible but nobody has submitted", async () => {
    open(
      dashboard({
        [ORG_URL]: () =>
          json(200, summary({ respondent_count: 0, eligible_count: 5, participation_rate: 0, average_score: null, suppressed: true })),
      }),
    );

    expect(await screen.findByText("No check-ins were submitted this month.")).toBeInTheDocument();
    expect(await metric("Participation")).toBe("0%");
    expect(await metric("Average score")).toBe("Insufficient responses");
  });

  it("shows a request failure and recovers when the user tries again", async () => {
    let calls = 0;
    open(
      dashboard({
        [ORG_URL]: () => {
          calls += 1;
          return calls === 1
            ? json(500, { error: { code: "internal_error", message: "Server error" } })
            : json(200, summary());
        },
      }),
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("We could not load the dashboard");
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));

    expect(await metric("Average score")).toBe("68.3");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("reports an unreachable server with the same retry option", async () => {
    open(dashboard({}));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Could not reach the server");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("keeps the team filter usable after a team request fails", async () => {
    open(
      dashboard({
        [ORG_URL]: () => json(200, summary()),
        [TEAM_URL]: () => json(500, { error: { code: "internal_error", message: "Server error" } }),
      }),
    );
    await metric("Average score");
    const user = userEvent.setup();

    await user.selectOptions(screen.getByLabelText("Team"), "Platform");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByLabelText("Team")).toBeEnabled();

    await user.selectOptions(screen.getByLabelText("Team"), "All teams");
    expect(await metric("Average score")).toBe("68.3");
  });
});
