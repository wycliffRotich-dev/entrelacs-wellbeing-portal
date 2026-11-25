import { ApiError, createApi } from "./client";

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function setup(respond: () => Promise<Response>, token: string | null = "tok") {
  const fetchFn = vi.fn<typeof fetch>(respond);
  const onUnauthorized = vi.fn();
  const api = createApi({ fetchFn, getToken: () => token, onUnauthorized });
  return { api, fetchFn, onUnauthorized };
}

test("sends the bearer token and a JSON body", async () => {
  const { api, fetchFn } = setup(async () => reply(200, { id: "c1" }));
  await api.saveDraft({ support: 4 });
  const [url, init] = fetchFn.mock.calls[0] ?? [];
  expect(url).toBe("/api/employee/check-ins/draft");
  expect(init?.method).toBe("PUT");
  expect(init?.headers).toMatchObject({
    Authorization: "Bearer tok",
    "Content-Type": "application/json",
  });
  expect(init?.body).toBe(JSON.stringify({ support: 4 }));
});

test("maps the error envelope to a typed ApiError", async () => {
  const { api } = setup(async () =>
    reply(422, {
      error: {
        code: "validation_error",
        message: "request validation failed",
        details: [{ field: "body.support", message: "too big" }],
      },
    }),
  );
  const error = await api.saveDraft({ support: 11 }).catch((e: unknown) => e);
  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({
    status: 422,
    code: "validation_error",
    details: [{ field: "body.support", message: "too big" }],
  });
});

test("a network failure becomes a retryable network_error", async () => {
  const { api } = setup(() => Promise.reject(new TypeError("Failed to fetch")));
  const error = await api.me().catch((e: unknown) => e);
  expect(error).toMatchObject({ status: 0, code: "network_error" });
});

test("a non-JSON error body becomes unexpected_response", async () => {
  const { api } = setup(async () => new Response("<html>bad gateway</html>", { status: 502 }));
  const error = await api.me().catch((e: unknown) => e);
  expect(error).toMatchObject({ status: 502, code: "unexpected_response" });
});

test("a 401 on an authenticated request signs the user out", async () => {
  const { api, onUnauthorized } = setup(async () =>
    reply(401, { error: { code: "not_authenticated", message: "authentication required" } }),
  );
  await api.me().catch(() => undefined);
  expect(onUnauthorized).toHaveBeenCalledOnce();
});

test("a 401 on login does not sign out, it is just wrong credentials", async () => {
  const { api, onUnauthorized } = setup(
    async () =>
      reply(401, { error: { code: "invalid_credentials", message: "invalid email or password" } }),
    null,
  );
  const error = await api.login("a@example.test", "bad").catch((e: unknown) => e);
  expect(error).toMatchObject({ status: 401, code: "invalid_credentials" });
  expect(onUnauthorized).not.toHaveBeenCalled();
});

test("wellbeing builds an encoded team filter only when one is given", async () => {
  const { api, fetchFn } = setup(async () => reply(200, {}));
  await api.wellbeing(null);
  await api.wellbeing("a b");
  expect(fetchFn.mock.calls.map(([url]) => url)).toEqual([
    "/api/hr/wellbeing",
    "/api/hr/wellbeing?team_id=a%20b",
  ]);
});
