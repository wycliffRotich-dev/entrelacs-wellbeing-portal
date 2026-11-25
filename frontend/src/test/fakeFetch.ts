type Handler = (body: unknown) => Response | Promise<Response>;

export function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Routes are keyed "METHOD /path". An unrouted request rejects, like an unreachable server. */
export function fakeFetch(routes: Record<string, Handler>) {
  return vi.fn<typeof fetch>(async (input, init) => {
    const key = `${init?.method ?? "GET"} ${String(input)}`;
    const handler = routes[key];
    if (handler === undefined) throw new Error(`unexpected request: ${key}`);
    const raw = init?.body;
    return handler(typeof raw === "string" ? JSON.parse(raw) : undefined);
  });
}
