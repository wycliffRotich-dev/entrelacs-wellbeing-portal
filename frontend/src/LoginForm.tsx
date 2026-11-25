import { useRef, useState, type FormEvent } from "react";

import { ApiError } from "./api/client";
import { useAuth } from "./auth";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "invalid_credentials") return "Incorrect email or password.";
    if (error.status === 0) return error.message;
  }
  return "Something went wrong. Please try again.";
}

interface FieldErrors {
  email: string | null;
  password: string | null;
}

export function LoginForm() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({ email: null, password: null });
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const inFlight = useRef(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (inFlight.current) return;
    const errors: FieldErrors = {
      email: email.trim() === "" ? "Enter your email address." : null,
      password: password === "" ? "Enter your password." : null,
    };
    setFieldErrors(errors);
    if (errors.email !== null || errors.password !== null) return;

    inFlight.current = true;
    setSubmitting(true);
    setFormError(null);
    try {
      await login(email.trim(), password);
    } catch (error) {
      setFormError(messageFor(error));
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  }

  return (
    <form className="card" onSubmit={onSubmit} noValidate aria-labelledby="login-title">
      <h1 id="login-title">Sign in</h1>
      {formError !== null && (
        <p role="alert" className="alert">
          {formError}
        </p>
      )}
      <div className="field">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-invalid={fieldErrors.email !== null}
          aria-describedby={fieldErrors.email !== null ? "email-error" : undefined}
        />
        {fieldErrors.email !== null && (
          <p id="email-error" className="field-error">
            {fieldErrors.email}
          </p>
        )}
      </div>
      <div className="field">
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={fieldErrors.password !== null}
          aria-describedby={fieldErrors.password !== null ? "password-error" : undefined}
        />
        {fieldErrors.password !== null && (
          <p id="password-error" className="field-error">
            {fieldErrors.password}
          </p>
        )}
      </div>
      <button type="submit" disabled={submitting}>
        {submitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
