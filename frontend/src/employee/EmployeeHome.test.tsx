import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { CheckIn } from "../api/types";
import { App } from "../App";
import { setToken } from "../session";
import { fakeFetch, json } from "../test/fakeFetch";

const EMPLOYEE = {
  id: "u1",
  email: "maya@northwind.example.test",
  role: "EMPLOYEE",
  organization_id: "o1",
  team_id: "t1",
};
const CURRENT = "GET /api/employee/check-ins/current";
const DRAFT_URL = "/api/employee/check-ins/draft";
const SUBMIT_URL = "/api/employee/check-ins/c1/submit";
const Q = {
  connectedness: "How connected do you feel to the people around you?",
  support: "How supported do you feel at work?",
  workload: "How manageable does your workload feel?",
};

function checkIn(over: Partial<CheckIn> = {}): CheckIn {
  return {
    id: "c1",
    status: "DRAFT",
    connectedness: null,
    support: null,
    workload: null,
    score: null,
    created_at: "2026-10-05T09:00:00Z",
    updated_at: "2026-10-05T09:00:00Z",
    submitted_at: null,
    ...over,
  };
}
const FULL_DRAFT = checkIn({ connectedness: 10, support: 10, workload: 9 });
const SUBMITTED = checkIn({
  status: "SUBMITTED",
  connectedness: 10,
  support: 10,
  workload: 9,
  score: 96.7,
  submitted_at: "2026-10-06T09:00:00Z",
});
const EMPTY_CURRENT = { draft: null, latest_submitted: null };

function open(routes: Parameters<typeof fakeFetch>[0]) {
  setToken("tok-1");
  const fetchFn = fakeFetch({ "GET /api/auth/me": () => json(200, EMPLOYEE), ...routes });
  render(<App fetchFn={fetchFn} />);
  return fetchFn;
}

function radio(question: keyof typeof Q, n: number) {
  return within(screen.getByRole("group", { name: Q[question] })).getByRole("radio", {
    name: String(n),
  });
}

function sent(fetchFn: ReturnType<typeof open>, method: string, url: string) {
  return fetchFn.mock.calls
    .filter(([u, init]) => u === url && init?.method === method)
    .map(([, init]) => (typeof init?.body === "string" ? JSON.parse(init.body) : undefined));
}

async function answerAll(user: ReturnType<typeof userEvent.setup>) {
  await user.click(radio("connectedness", 10));
  await user.click(radio("support", 10));
  await user.click(radio("workload", 9));
}

const formName = { name: "Wellbeing check-in" };

test("a new employee sees the empty state and a labelled form with all three questions", async () => {
  open({ [CURRENT]: () => json(200, EMPTY_CURRENT) });
  expect(await screen.findByRole("form", formName)).toBeInTheDocument();
  expect(screen.getByText("You have not submitted a check-in yet.")).toBeInTheDocument();
  expect(screen.getAllByRole("radio")).toHaveLength(33);
  for (const label of Object.values(Q)) {
    expect(screen.getByRole("group", { name: label })).toBeInTheDocument();
  }
});

test("a saved draft is restored when the employee returns", async () => {
  open({ [CURRENT]: () => json(200, { draft: checkIn({ connectedness: 7 }), latest_submitted: null }) });
  await screen.findByRole("form", formName);
  expect(radio("connectedness", 7)).toBeChecked();
  expect(radio("support", 7)).not.toBeChecked();
  expect(screen.getByText("Continuing your saved draft.")).toBeInTheDocument();
});

test("a partial draft can be saved without submitting", async () => {
  const fetchFn = open({
    [CURRENT]: () => json(200, EMPTY_CURRENT),
    [`PUT ${DRAFT_URL}`]: () => json(200, checkIn({ connectedness: 7 })),
  });
  const user = userEvent.setup();
  await screen.findByRole("form", formName);
  expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();
  await user.click(radio("connectedness", 7));
  await user.click(screen.getByRole("button", { name: "Save draft" }));
  expect(await screen.findByText("Draft saved.")).toBeInTheDocument();
  expect(sent(fetchFn, "PUT", DRAFT_URL)).toEqual([{ connectedness: 7 }]);
  expect(sent(fetchFn, "POST", SUBMIT_URL)).toHaveLength(0);
  expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();
});

test("when saving fails the entered answers are kept and the user can retry", async () => {
  open({
    [CURRENT]: () => json(200, EMPTY_CURRENT),
    [`PUT ${DRAFT_URL}`]: () => {
      throw new TypeError("Failed to fetch");
    },
  });
  const user = userEvent.setup();
  await screen.findByRole("form", formName);
  await user.click(radio("connectedness", 7));
  await user.click(screen.getByRole("button", { name: "Save draft" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server");
  expect(radio("connectedness", 7)).toBeChecked();
  expect(screen.getByRole("button", { name: "Save draft" })).toBeEnabled();
});

test("submitting with unanswered questions shows inline errors and calls nothing", async () => {
  const fetchFn = open({ [CURRENT]: () => json(200, EMPTY_CURRENT) });
  const user = userEvent.setup();
  await screen.findByRole("form", formName);
  await user.click(radio("support", 4));
  await user.click(screen.getByRole("button", { name: "Submit check-in" }));
  expect(screen.getAllByText("Choose an answer from 0 to 10.")).toHaveLength(2);
  expect(screen.getByRole("alert")).toHaveTextContent("Answer all three questions");
  expect(sent(fetchFn, "PUT", DRAFT_URL)).toHaveLength(0);
  expect(sent(fetchFn, "POST", SUBMIT_URL)).toHaveLength(0);
});

test("a complete check-in is saved, submitted, and its score and answers are shown", async () => {
  const fetchFn = open({
    [CURRENT]: () => json(200, EMPTY_CURRENT),
    [`PUT ${DRAFT_URL}`]: () => json(200, FULL_DRAFT),
    [`POST ${SUBMIT_URL}`]: () => json(200, SUBMITTED),
  });
  const user = userEvent.setup();
  await screen.findByRole("form", formName);
  await answerAll(user);
  await user.click(screen.getByRole("button", { name: "Submit check-in" }));
  expect(await screen.findByText("96.7")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Your latest result" })).toBeInTheDocument();
  expect(screen.queryAllByRole("radio")).toHaveLength(0);
  expect(screen.getByRole("button", { name: "Start a new check-in" })).toBeInTheDocument();
  const writes = fetchFn.mock.calls
    .filter(([, init]) => init?.method !== "GET")
    .map(([url]) => url);
  expect(writes).toEqual([DRAFT_URL, SUBMIT_URL]);
});

test("a double click on submit sends one save and one submit", async () => {
  let release: (response: Response) => void = () => undefined;
  const pending = new Promise<Response>((resolve) => {
    release = resolve;
  });
  const fetchFn = open({
    [CURRENT]: () => json(200, EMPTY_CURRENT),
    [`PUT ${DRAFT_URL}`]: () => pending,
    [`POST ${SUBMIT_URL}`]: () => json(200, SUBMITTED),
  });
  const user = userEvent.setup();
  await screen.findByRole("form", formName);
  await answerAll(user);
  const submit = screen.getByRole("button", { name: "Submit check-in" });
  await user.click(submit);
  await user.click(submit);
  release(json(200, FULL_DRAFT));
  await screen.findByText("96.7");
  expect(sent(fetchFn, "PUT", DRAFT_URL)).toHaveLength(1);
  expect(sent(fetchFn, "POST", SUBMIT_URL)).toHaveLength(1);
});

test("the latest submitted check-in is read-only and a new one can be started", async () => {
  open({ [CURRENT]: () => json(200, { draft: null, latest_submitted: SUBMITTED }) });
  expect(await screen.findByRole("heading", { name: "Your latest result" })).toBeInTheDocument();
  expect(screen.queryAllByRole("radio")).toHaveLength(0);
  await userEvent.setup().click(screen.getByRole("button", { name: "Start a new check-in" }));
  expect(await screen.findByRole("form", formName)).toBeInTheDocument();
  expect(screen.getAllByRole("radio")).toHaveLength(33);
  expect(screen.getByRole("heading", { name: "Your previous check-in" })).toBeInTheDocument();
});

test("a failed load shows a retryable error and then the form", async () => {
  let attempts = 0;
  open({
    [CURRENT]: () => {
      attempts += 1;
      if (attempts === 1) throw new TypeError("Failed to fetch");
      return json(200, EMPTY_CURRENT);
    },
  });
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server");
  await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("form", formName)).toBeInTheDocument();
});

test("a check-in already submitted elsewhere is reported and the result is shown", async () => {
  let loads = 0;
  open({
    [CURRENT]: () => {
      loads += 1;
      return json(200, loads === 1 ? EMPTY_CURRENT : { draft: null, latest_submitted: SUBMITTED });
    },
    [`PUT ${DRAFT_URL}`]: () => json(200, FULL_DRAFT),
    [`POST ${SUBMIT_URL}`]: () =>
      json(409, { error: { code: "check_in_already_submitted", message: "already submitted" } }),
  });
  const user = userEvent.setup();
  await screen.findByRole("form", formName);
  await answerAll(user);
  await user.click(screen.getByRole("button", { name: "Submit check-in" }));
  expect(await screen.findByRole("heading", { name: "Your latest result" })).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("already submitted");
});
