import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiError, createApi, type Api } from "./api/client";
import type { Me } from "./api/types";
import { clearToken, getToken, setToken } from "./session";

type AuthState =
  | { status: "loading"; user: null }
  | { status: "anonymous"; user: null }
  | { status: "unavailable"; user: null }
  | { status: "authenticated"; user: Me };

interface AuthValue {
  state: AuthState;
  api: Api;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  retry: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({
  children,
  fetchFn,
}: {
  children: ReactNode;
  fetchFn?: typeof fetch;
}) {
  const [state, setState] = useState<AuthState>({ status: "loading", user: null });

  const logout = useCallback(() => {
    clearToken();
    setState({ status: "anonymous", user: null });
  }, []);

  const api = useMemo(
    () => createApi({ fetchFn, getToken, onUnauthorized: logout }),
    [fetchFn, logout],
  );

  const restore = useCallback(async () => {
    if (getToken() === null) {
      setState({ status: "anonymous", user: null });
      return;
    }
    setState({ status: "loading", user: null });
    try {
      setState({ status: "authenticated", user: await api.me() });
    } catch (error) {
      if (error instanceof ApiError && error.status === 0) {
        setState({ status: "unavailable", user: null });
      } else {
        logout();
      }
    }
  }, [api, logout]);

  useEffect(() => {
    void restore();
  }, [restore]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await api.login(email, password);
      setToken(access_token);
      try {
        setState({ status: "authenticated", user: await api.me() });
      } catch (error) {
        clearToken();
        throw error;
      }
    },
    [api],
  );

  const value = useMemo(
    () => ({ state, api, login, logout, retry: () => void restore() }),
    [state, api, login, logout, restore],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (value === null) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
