import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "./App";
import { getToken, setToken } from "./session";
import { fakeFetch, json } from "./test/fakeFetch";

const EMPLOYEE = {
  id: "u1",
  email: "maya@northwind.example.test",
  role: "EMPLOYEE",
  organization_id: "o1",
  team_id: "t1",
};
const HR = { ...EMPLOYEE, email: "hr@northwind.example.test", role: "HR", team_id: null };
const TOKEN = { access_token: "tok-1", token_type: "bearer" };
const INVALID = { error: { code: "invalid_credentials", message: "invalid email or password" } };
const UNAUTH = { error: { code: "not_authenticated", message: "authentication required" } };

async function signIn(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText("Email"), "maya@northwind.example.test");
  await user.type(screen.getByLabelText("Password"), "pw");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
}

test("shows the sign-in form when there is no session", async () => {
  render(<App fetchFn={fakeFetch({})} />);
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("an employee signs in and lands on the check-in screen", async () => {
  const fetchFn = fakeFetch({
    "POST /api/auth/login": () => json(200, TOKEN),
    "GET /api/auth/me": () => json(200, EMPLOYEE),
  });
  const user = userEvent.setup();
  render(<App fetchFn={fetchFn} />);
  await signIn(user);
  expect(await screen.findByRole("heading", { name: "Your check-in" })).toBeInTheDocument();
  expect(screen.getByText("maya@northwind.example.test")).toBeInTheDocument();
  expect(getToken()).toBe("tok-1");
});

test("wrong credentials show one generic error and keep the user on the form", async () => {
  const fetchFn = fakeFetch({ "POST /api/auth/login": () => json(401, INVALID) });
  const user = userEvent.setup();
  render(<App fetchFn={fetchFn} />);
  await signIn(user);
  expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
  expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(getToken()).toBeNull();
});

test("empty fields are rejected locally without calling the API", async () => {
  const fetchFn = fakeFetch({});
  const user = userEvent.setup();
  render(<App fetchFn={fetchFn} />);
  await user.click(await screen.findByRole("button", { name: "Sign in" }));
  expect(screen.getByText("Enter your email address.")).toBeInTheDocument();
  expect(screen.getByText("Enter your password.")).toBeInTheDocument();
  expect(fetchFn).not.toHaveBeenCalled();
});

test("a stored session is restored after a refresh and routed by role", async () => {
  setToken("tok-1");
  const fetchFn = fakeFetch({ "GET /api/auth/me": () => json(200, HR) });
  render(<App fetchFn={fetchFn} />);
  expect(await screen.findByRole("heading", { name: "Organization wellbeing" })).toBeInTheDocument();
});

test("a stale token returns the user to sign-in and is discarded", async () => {
  setToken("stale");
  const fetchFn = fakeFetch({ "GET /api/auth/me": () => json(401, UNAUTH) });
  render(<App fetchFn={fetchFn} />);
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(getToken()).toBeNull();
});

test("a second click while signing in does not send a second login request", async () => {
  let release: (response: Response) => void = () => undefined;
  const pending = new Promise<Response>((resolve) => {
    release = resolve;
  });
  const fetchFn = fakeFetch({
    "POST /api/auth/login": () => pending,
    "GET /api/auth/me": () => json(200, EMPLOYEE),
  });
  const user = userEvent.setup();
  render(<App fetchFn={fetchFn} />);
  await user.type(await screen.findByLabelText("Email"), "maya@northwind.example.test");
  await user.type(screen.getByLabelText("Password"), "pw");
  const button = screen.getByRole("button", { name: "Sign in" });
  await user.click(button);
  await user.click(button);
  release(json(200, TOKEN));
  await screen.findByRole("heading", { name: "Your check-in" });
  const logins = fetchFn.mock.calls.filter(([url]) => url === "/api/auth/login");
  expect(logins).toHaveLength(1);
});

test("signing out clears the session and returns to the form", async () => {
  const fetchFn = fakeFetch({
    "POST /api/auth/login": () => json(200, TOKEN),
    "GET /api/auth/me": () => json(200, EMPLOYEE),
  });
  const user = userEvent.setup();
  render(<App fetchFn={fetchFn} />);
  await signIn(user);
  await user.click(await screen.findByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(getToken()).toBeNull();
});

test("an unreachable server on restore offers a retry instead of signing out", async () => {
  setToken("tok-1");
  let attempts = 0;
  const fetchFn = fakeFetch({
    "GET /api/auth/me": () => {
      attempts += 1;
      if (attempts === 1) throw new TypeError("Failed to fetch");
      return json(200, EMPLOYEE);
    },
  });
  const user = userEvent.setup();
  render(<App fetchFn={fetchFn} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("We could not reach the server.");
  expect(getToken()).toBe("tok-1");
  await user.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("heading", { name: "Your check-in" })).toBeInTheDocument();
});
