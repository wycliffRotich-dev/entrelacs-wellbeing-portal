import { AuthProvider, useAuth } from "./auth";
import { EmployeeHome } from "./employee/EmployeeHome";
import { HrHome } from "./hr/HrHome";
import { LoginForm } from "./LoginForm";

function Shell() {
  const { state, logout, retry } = useAuth();

  if (state.status === "loading") {
    return (
      <main className="container">
        <p role="status">Loading…</p>
      </main>
    );
  }
  if (state.status === "unavailable") {
    return (
      <main className="container">
        <div role="alert" className="alert">
          <p>We could not reach the server.</p>
          <button type="button" onClick={retry}>
            Try again
          </button>
        </div>
      </main>
    );
  }
  if (state.status === "anonymous") {
    return (
      <main className="container">
        <LoginForm />
      </main>
    );
  }
  return (
    <>
      <header className="app-header">
        <span>{state.user.email}</span>
        <button type="button" className="secondary" onClick={logout}>
          Sign out
        </button>
      </header>
      <main className="container">{state.user.role === "HR" ? <HrHome /> : <EmployeeHome />}</main>
    </>
  );
}

export function App({ fetchFn }: { fetchFn?: typeof fetch }) {
  return (
    <AuthProvider fetchFn={fetchFn}>
      <Shell />
    </AuthProvider>
  );
}
