import type {
  CheckIn,
  CurrentCheckIns,
  DraftInput,
  Me,
  Team,
  TokenResponse,
  Wellbeing,
} from "./types";

export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: FieldError[];

  constructor(status: number, code: string, message: string, details: FieldError[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export interface ApiOptions {
  fetchFn?: typeof fetch;
  getToken: () => string | null;
  onUnauthorized: () => void;
  timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 15_000;
const UNEXPECTED = "Unexpected response from the server.";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function readError(response: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return new ApiError(response.status, "unexpected_response", UNEXPECTED);
  }
  const error = isRecord(body) ? body.error : undefined;
  if (!isRecord(error) || typeof error.code !== "string") {
    return new ApiError(response.status, "unexpected_response", UNEXPECTED);
  }
  const details = Array.isArray(error.details)
    ? error.details.filter(isRecord).flatMap((d) =>
        typeof d.field === "string" && typeof d.message === "string"
          ? [{ field: d.field, message: d.message }]
          : [],
      )
    : [];
  const message = typeof error.message === "string" ? error.message : UNEXPECTED;
  return new ApiError(response.status, error.code, message, details);
}

export function createApi(options: ApiOptions) {
  const fetchFn = options.fetchFn ?? ((input, init) => fetch(input, init));
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const token = options.getToken();
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (token !== null) headers["Authorization"] = `Bearer ${token}`;

    let response: Response;
    try {
      response = await fetchFn(path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(timeoutMs),
      });
    } catch {
      throw new ApiError(
        0,
        "network_error",
        "Could not reach the server. Check your connection and try again.",
      );
    }

    if (!response.ok) {
      if (response.status === 401 && token !== null) options.onUnauthorized();
      throw await readError(response);
    }
    try {
      return (await response.json()) as T;
    } catch {
      throw new ApiError(response.status, "unexpected_response", UNEXPECTED);
    }
  }

  return {
    login: (email: string, password: string) =>
      request<TokenResponse>("POST", "/api/auth/login", { email, password }),
    me: () => request<Me>("GET", "/api/auth/me"),
    currentCheckIns: () => request<CurrentCheckIns>("GET", "/api/employee/check-ins/current"),
    saveDraft: (input: DraftInput) =>
      request<CheckIn>("PUT", "/api/employee/check-ins/draft", input),
    submitCheckIn: (id: string) =>
      request<CheckIn>("POST", `/api/employee/check-ins/${encodeURIComponent(id)}/submit`),
    getCheckIn: (id: string) =>
      request<CheckIn>("GET", `/api/employee/check-ins/${encodeURIComponent(id)}`),
    wellbeing: (teamId: string | null) =>
      request<Wellbeing>(
        "GET",
        teamId === null
          ? "/api/hr/wellbeing"
          : `/api/hr/wellbeing?team_id=${encodeURIComponent(teamId)}`,
      ),
    teams: () => request<Team[]>("GET", "/api/hr/teams"),
  };
}

export type Api = ReturnType<typeof createApi>;
