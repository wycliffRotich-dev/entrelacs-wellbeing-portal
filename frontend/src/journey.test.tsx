import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "./App";
import { getToken } from "./session";
import { fakeFetch, json } from "./test/fakeFetch";

const EMPLOYEE = {
  id: "u1",
  email: "maya@northwind.example.test",
  role: "EMPLOYEE",
  organization_id: "o1",
  team_id: "t1",
};
const HR = {
  id: "h1",
  email: "hr@northwind.example.test",
  role: "HR",
  organization_id: "o1",
  team_id: null,
};
const ACCOUNTS = { [EMPLOYEE.email]: EMPLOYEE, [HR.email]: HR } as Record<string, { role: string }>;
const TOKEN = { access_token: "tok-1", token_type: "bearer" };
const FORBIDDEN = { error: { code: "forbidden", message: "Forbidden" } };
const Q = {
  connectedness: "How connected do you feel to the people around you?",
  support: "How supported do you feel at work?",
  workload: "How manageable does your workload feel?",
};
const SUBMITTED = {
  id: "c1",
  status: "SUBMITTED",
  connectedness: 10,
  support: 10,
  workload: 9,
  score: 96.7,
  created_at: "2026-10-05T09:00:00Z",
  updated_at: "2026-10-05T09:00:00Z",
  submitted_at: "2026-10-05T09:01:00Z",
};
const DRAFT = { ...SUBMITTED, status: "DRAFT", score: null, submitted_at: null };

/** One fake backend for both roles. Routes answer 403 when the signed-in role does not match. */
function fakeServer() {
  let signedIn: { role: string } | null = null;
  let submitted = false;
  const only = (role: string, respond: () => Response) => (): Response =>
    signedIn?.role === role ? respond() : json(403, FORBIDDEN);

  return fakeFetch({
    "POST /api/auth/login": (body) => {
      const account = ACCOUNTS[(body as { email: string }).email];
      if (account === undefined) {
        return json(401, { error: { code: "invalid_credentials", message: "Invalid" } });
      }
      signedIn = account;
      return json(200, TOKEN);
    },
    "GET /api/auth/me": () =>
      signedIn === null
        ? json(401, { error: { code: "unauthorized", message: "Unauthorized" } })
        : json(200, signedIn),
    "GET /api/employee/check-ins/current": only("EMPLOYEE", () =>
      json(200, { draft: null, latest_submitted: submitted ? SUBMITTED : null }),
    ),
    "PUT /api/employee/check-ins/draft": only("EMPLOYEE", () => json(200, DRAFT)),
    "POST /api/employee/check-ins/c1/submit": only("EMPLOYEE", () => {
      submitted = true;
      return json(200, SUBMITTED);
    }),
    "GET /api/hr/teams": only("HR", () => json(200, [{ id: "t1", name: "Platform" }])),
    "GET /api/hr/wellbeing": only("HR", () =>
      json(200, {
        reporting_month: "2026-10",
        team_id: null,
        respondent_count: submitted ? 1 : 0,
        eligible_count: 14,
        participation_rate: submitted ? 7.1 : 0,
        average_score: null,
        suppressed: true,
      }),
    ),
  });
}

async function signIn(user: ReturnType<typeof userEvent.setup>, email: string) {
  await user.type(screen.getByLabelText("Email"), email);
  await user.type(screen.getByLabelText("Password"), "demo-password-123");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
}

function radio(question: keyof typeof Q, n: number) {
  return within(screen.getByRole("group", { name: Q[question] })).getByRole("radio", {
    name: String(n),
  });
}

async function metric(label: string): Promise<string> {
  const term = await screen.findByText(label, { selector: "dt" });
  return term.nextElementSibling?.textContent ?? "";
}

test("an employee submits a check-in and HR then sees only the aggregate", async () => {
  const user = userEvent.setup();
  render(<App fetchFn={fakeServer()} />);

  // Employee: sign in, answer, submit, see the server-calculated score.
  await signIn(user, EMPLOYEE.email);
  await screen.findByRole("form", { name: "Wellbeing check-in" });
  await user.click(radio("connectedness", 10));
  await user.click(radio("support", 10));
  await user.click(radio("workload", 9));
  await user.click(screen.getByRole("button", { name: "Submit check-in" }));
  expect(await screen.findByText("96.7")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Your latest result" })).toBeInTheDocument();

  // Sign out clears the session completely.
  await user.click(screen.getByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(getToken()).toBeNull();

  // HR: sign in and see the aggregate that the submission produced.
  await signIn(user, HR.email);
  expect(await screen.findByRole("heading", { name: "Organization wellbeing" })).toBeInTheDocument();
  expect(await metric("Respondents")).toBe("1");
  expect(await metric("Participation")).toBe("7.1%");
  expect(await metric("Average score")).toBe("Insufficient responses");

  // HR sees no individual score and no employee identity.
  expect(screen.queryByText("96.7")).not.toBeInTheDocument();
  expect(screen.queryByText(/maya@/)).not.toBeInTheDocument();
});
