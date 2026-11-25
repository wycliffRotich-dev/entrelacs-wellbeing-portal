const KEY = "wellbeing.token";

// Kept in memory as well, so a blocked sessionStorage still allows a session for this page load.
let memory: string | null = null;

export function getToken(): string | null {
  if (memory !== null) return memory;
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  memory = token;
  try {
    sessionStorage.setItem(KEY, token);
  } catch {
    // Storage unavailable: the session lasts until the page reloads.
  }
}

export function clearToken(): void {
  memory = null;
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // Nothing to clear.
  }
}
