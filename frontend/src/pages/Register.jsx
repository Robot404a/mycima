import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Check, Eye, EyeOff, TriangleAlert } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { apiErrorMessage } from "../lib/api";
import { useDocumentTitle } from "../lib/hooks";
import { AuthShell } from "../components/AuthShell";
import { Spinner } from "../components/Feedback";

const RULES = [
  { key: "length", label: "8 characters minimum", test: (value) => value.length >= 8 },
  { key: "letter", label: "One letter", test: (value) => /[a-zA-ZÀ-ÿ]/.test(value) },
  { key: "number", label: "One number", test: (value) => /\d/.test(value) },
];

export default function Register() {
  useDocumentTitle("Join MyCima");
  const { register, isAuthenticated } = useAuth();
  const { pushToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    password: "",
    confirm: "",
  });
  const [accepted, setAccepted] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [duplicate, setDuplicate] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const from = location.state?.from || "/";

  const passed = useMemo(
    () => RULES.map((rule) => ({ ...rule, ok: rule.test(form.password) })),
    [form.password],
  );
  const strong = passed.filter((rule) => rule.ok).length >= 3;

  useEffect(() => {
    if (isAuthenticated) navigate(from, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  const update = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    setError("");
    setDuplicate(false);
    if (form.full_name.trim().length < 2) return setError("Please enter your full name.");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) return setError("Enter a valid email address.");
    if (!strong) return setError("Choose a stronger password — at least 8 characters with a letter and a number.");
    if (form.password !== form.confirm) return setError("The passwords do not match.");
    if (!accepted) return setError("Please accept the house rules to continue.");
    setSubmitting(true);
    try {
      const account = await register({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim() || null,
        password: form.password,
      });
      pushToast(`Welcome to MyCima${account?.full_name ? `, ${account.full_name.split(" ")[0]}` : ""}.`, "success");
      navigate(from, { replace: true });
    } catch (err) {
      if (err?.status === 409) setDuplicate(true);
      setError(apiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell
      eyebrow="Join the house"
      title="Your seat is waiting."
      subtitle="Create an account to hold seats, keep your tickets and let the concierge learn what you like."
      side="register"
      footer={
        <p>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      }
    >
      <form className="auth-form" onSubmit={submit} noValidate>
        {error ? (
          <div className="inline-banner inline-banner--error" role="alert">
            <TriangleAlert size={16} />
            <span>
              {error}{" "}
              {duplicate ? <Link to="/login">Sign in instead</Link> : null}
            </span>
          </div>
        ) : null}
        <div className="field-grid">
          <label className="field field--full">
            <span>Full name</span>
            <input
              type="text"
              value={form.full_name}
              onChange={update("full_name")}
              placeholder="Your name"
              autoComplete="name"
              autoFocus
              required
            />
          </label>
          <label className="field field--full">
            <span>Email</span>
            <input
              type="email"
              value={form.email}
              onChange={update("email")}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
          </label>
          <label className="field field--full">
            <span>
              Phone <small className="field-optional">optional</small>
            </span>
            <input
              type="tel"
              value={form.phone}
              onChange={update("phone")}
              placeholder="+212 6 00 00 00 00"
              autoComplete="tel"
            />
          </label>
          <label className="field">
            <span>Password</span>
            <div className="input-with-action">
              <input
                type={showPassword ? "text" : "password"}
                value={form.password}
                onChange={update("password")}
                placeholder="At least 8 characters"
                autoComplete="new-password"
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
          <label className="field">
            <span>Confirm password</span>
            <input
              type={showPassword ? "text" : "password"}
              value={form.confirm}
              onChange={update("confirm")}
              placeholder="Repeat your password"
              autoComplete="new-password"
              required
              aria-invalid={Boolean(form.confirm) && form.confirm !== form.password}
            />
          </label>
        </div>
        <div className="password-rules" aria-label="Password requirements">
          {passed.map((rule) => (
            <span key={rule.key} className={rule.ok ? "is-ok" : ""}>
              <Check size={12} /> {rule.label}
            </span>
          ))}
        </div>
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={accepted}
            onChange={(event) => setAccepted(event.target.checked)}
          />
          <span>
            I accept the house rules and the simulated nature of payments in this project.
          </span>
        </label>
        <button type="submit" className="btn btn--gold btn--block btn--lg" disabled={submitting}>
          {submitting ? (
            <>
              <Spinner size={16} label="Creating your account" /> Creating your account…
            </>
          ) : (
            <>
              Create my account <ArrowRight size={15} />
            </>
          )}
        </button>
        <div className="auth-hint-row">
          <span>Your account is secured with JWT and hashed passwords.</span>
          <Link to="/login">I already have an account</Link>
        </div>
      </form>
    </AuthShell>
  );
}
