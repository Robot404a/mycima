import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Eye, EyeOff, TriangleAlert } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { apiErrorMessage } from "../lib/api";
import { useDocumentTitle } from "../lib/hooks";
import { AuthShell } from "../components/AuthShell";
import { Spinner } from "../components/Feedback";

export default function Login() {
  useDocumentTitle("Sign in");
  const { login, isAuthenticated, user } = useAuth();
  const { pushToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const from = location.state?.from || "/";

  useEffect(() => {
    if (isAuthenticated) {
      navigate(from.startsWith("/admin") && user?.role !== "admin" ? "/" : from, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  const submit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    setError("");
    if (!form.email.trim() || !form.password) {
      setError("Enter your email and password.");
      return;
    }
    setSubmitting(true);
    try {
      const account = await login(form.email.trim(), form.password);
      pushToast(`Welcome back${account.full_name ? `, ${account.full_name.split(" ")[0]}` : ""}.`, "success");
      navigate(from.startsWith("/admin") && account.role !== "admin" ? "/" : from, { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell
      eyebrow="Good evening"
      title="Welcome back."
      subtitle="Sign in to see your bookings, notifications and the seats waiting for you."
      footer={
        <p>
          New to MyCima? <Link to="/register">Create an account</Link>
        </p>
      }
    >
      <form className="auth-form" onSubmit={submit} noValidate>
        {error ? (
          <div className="inline-banner inline-banner--error" role="alert">
            <TriangleAlert size={16} /> {error}
          </div>
        ) : null}
        <label className="field">
          <span>Email</span>
          <input
            type="email"
            value={form.email}
            onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
            placeholder="you@example.com"
            autoComplete="email"
            autoFocus
            required
          />
        </label>
        <label className="field">
          <span>Password</span>
          <div className="input-with-action">
            <input
              type={showPassword ? "text" : "password"}
              value={form.password}
              onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              placeholder="Your password"
              autoComplete="current-password"
              required
            />
            <button
              type="button"
              className="input-action"
              onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </label>
        <button type="submit" className="btn btn--gold btn--block btn--lg" disabled={submitting}>
          {submitting ? (
            <>
              <Spinner size={16} label="Signing in" /> Signing in…
            </>
          ) : (
            <>
              Sign in <ArrowRight size={15} />
            </>
          )}
        </button>
        <div className="auth-hint-row">
          <span>Your account is secured with JWT and hashed passwords.</span>
          <Link to="/register">Need an account?</Link>
        </div>
      </form>
    </AuthShell>
  );
}
