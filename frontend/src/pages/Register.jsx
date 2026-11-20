import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, Eye, EyeOff, MailCheck, TriangleAlert } from "lucide-react";
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

const RESEND_SECONDS = 30;

export default function Register() {
  useDocumentTitle("Join Nocturne");
  const { startRegistration, verifyRegistration, resendRegistrationCode, isAuthenticated } = useAuth();
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
  const [step, setStep] = useState("details");
  const [pending, setPending] = useState(null);
  const [code, setCode] = useState("");
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);
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

  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const timer = window.setTimeout(() => setCooldown((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  const update = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  const submitDetails = async (event) => {
    event.preventDefault();
    if (submitting) return;
    setError("");
    if (form.full_name.trim().length < 2) return setError("Please enter your full name.");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) return setError("Enter a valid email address.");
    if (!strong) return setError("Choose a stronger password — at least 8 characters with a letter and a number.");
    if (form.password !== form.confirm) return setError("The passwords do not match.");
    if (!accepted) return setError("Please accept the house rules to continue.");
    setSubmitting(true);
    try {
      const result = await startRegistration({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim() || null,
        password: form.password,
      });
      setPending(result);
      setCode("");
      setStep("code");
      setCooldown(RESEND_SECONDS);
      pushToast(`We sent a 6-digit code to ${result.email}.`, "success");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const submitCode = async (event) => {
    event.preventDefault();
    if (verifying || !pending) return;
    setError("");
    if (!/^\d{6}$/.test(code)) return setError("Enter the 6-digit code from the email.");
    setVerifying(true);
    try {
      const account = await verifyRegistration(pending.email, code);
      pushToast(`Welcome to Nocturne${account?.full_name ? `, ${account.full_name.split(" ")[0]}` : ""}.`, "success");
      navigate(from, { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setVerifying(false);
    }
  };

  const resend = async () => {
    if (!pending || cooldown > 0 || resending) return;
    setResending(true);
    setError("");
    try {
      const result = await resendRegistrationCode(pending.email);
      setPending(result);
      setCode("");
      setCooldown(RESEND_SECONDS);
      pushToast("A fresh code is on its way.", "success");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setResending(false);
    }
  };

  const onCode = step === "code";

  return (
    <AuthShell
      eyebrow={onCode ? "One last step" : "Join the house"}
      title={onCode ? "Check your inbox." : "Your seat is waiting."}
      subtitle={
        onCode
          ? "Enter the 6-digit code we emailed you to prove the address is yours and finish setting up your account."
          : "Create an account to hold seats, keep your tickets and let the concierge learn what you like."
      }
      side="register"
      footer={
        <p>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      }
    >
      {onCode ? (
        <form className="auth-form" onSubmit={submitCode} noValidate>
          {error ? (
            <div className="inline-banner inline-banner--error" role="alert">
              <TriangleAlert size={16} /> {error}
            </div>
          ) : null}
          <div className="verify-summary">
            <MailCheck size={18} />
            <div>
              <strong>{pending?.email}</strong>
              <span>
                {pending?.delivered
                  ? "The code is in your inbox. It expires in 10 minutes."
                  : "Simulated inbox — email delivery is not configured, so the code is shown below."}
              </span>
            </div>
          </div>
          {pending?.dev_code ? (
            <div className="verify-hint">
              Development code: <strong>{pending.dev_code}</strong>
            </div>
          ) : null}
          <label className="field">
            <span>Verification code</span>
            <input
              className="code-input"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="000000"
              autoFocus
              required
            />
          </label>
          <button
            type="submit"
            className="btn btn--gold btn--block btn--lg"
            disabled={verifying || code.length !== 6}
          >
            {verifying ? (
              <>
                <Spinner size={16} label="Verifying code" /> Verifying…
              </>
            ) : (
              <>
                Verify and finish <ArrowRight size={15} />
              </>
            )}
          </button>
          <div className="verify-actions">
            <button
              type="button"
              className="text-btn"
              onClick={() => {
                setStep("details");
                setError("");
              }}
              disabled={verifying}
            >
              <ArrowLeft size={12} /> Change details
            </button>
            <span>
              {cooldown > 0 ? (
                `Resend in ${cooldown}s`
              ) : (
                <button type="button" className="text-btn" onClick={resend} disabled={resending}>
                  {resending ? "Sending…" : "Resend the code"}
                </button>
              )}
            </span>
          </div>
          <div className="auth-hint-row">
            <span>Codes are single-use and expire after 10 minutes.</span>
            <Link to="/login">I already have an account</Link>
          </div>
        </form>
      ) : (
        <form className="auth-form" onSubmit={submitDetails} noValidate>
          {error ? (
            <div className="inline-banner inline-banner--error" role="alert">
              <TriangleAlert size={16} /> {error}
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
                <Spinner size={16} label="Sending verification code" /> Sending your code…
              </>
            ) : (
              <>
                Continue <ArrowRight size={15} />
              </>
            )}
          </button>
          <div className="auth-hint-row">
            <span>We email a 6-digit code to confirm your address.</span>
            <Link to="/login">I already have an account</Link>
          </div>
        </form>
      )}
    </AuthShell>
  );
}
