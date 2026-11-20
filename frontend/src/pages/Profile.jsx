import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Bell,
  CalendarDays,
  Check,
  Mail,
  Phone,
  Settings2,
  ShieldCheck,
  Sparkles,
  Ticket,
  UserRound,
} from "lucide-react";
import { api, apiErrorMessage } from "../lib/api";
import { useApi, useDocumentTitle } from "../lib/hooks";
import { formatDateLong, initials, money } from "../lib/format";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { PageLoader, Skeleton, Spinner } from "../components/Feedback";

export default function Profile() {
  useDocumentTitle("Your profile");
  const { user, updateUser, logout } = useAuth();
  const { pushToast } = useToast();
  const [form, setForm] = useState({
    full_name: user?.full_name || "",
    phone: user?.phone || "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const summaryLoader = useCallback(async () => {
    const [bookings, unread] = await Promise.all([
      api("/bookings/me"),
      api("/notifications/unread-count"),
    ]);
    return { bookings, unread };
  }, []);
  const summary = useApi(summaryLoader, []);

  const stats = useMemo(() => {
    const items = summary.data?.bookings?.items || [];
    const now = Date.now();
    const upcoming = items.filter(
      (booking) => booking.status === "CONFIRMED" && new Date(booking.starts_at).getTime() >= now,
    );
    const spend = items
      .filter((booking) => booking.status === "CONFIRMED")
      .reduce((sum, booking) => sum + Number(booking.total_price || 0), 0);
    return {
      upcoming: upcoming.length,
      total: items.length,
      spend,
      unread: summary.data?.unread?.unread || 0,
    };
  }, [summary.data]);

  const dirty =
    form.full_name.trim() !== (user?.full_name || "") ||
    form.phone.trim() !== (user?.phone || "");

  const save = async (event) => {
    event.preventDefault();
    if (saving) return;
    setError("");
    if (form.full_name.trim().length < 2) {
      setError("Your name needs at least two characters.");
      return;
    }
    setSaving(true);
    try {
      const updated = await api("/users/me", {
        method: "PATCH",
        body: { full_name: form.full_name.trim(), phone: form.phone.trim() || null },
      });
      updateUser(updated);
      setForm({ full_name: updated.full_name, phone: updated.phone || "" });
      pushToast("Profile updated.", "success");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  if (!user) return <PageLoader label="Opening your profile" />;

  return (
    <div className="profile-page page">
      <header className="profile-head">
        <div className="profile-identity">
          <span className="avatar avatar--xl">{initials(user.full_name)}</span>
          <div>
            <span className="eyebrow">Member since {formatDateLong(user.created_at)}</span>
            <h1>{user.full_name}</h1>
            <div className="profile-chips">
              <span className="profile-chip">
                <Mail size={13} /> {user.email}
              </span>
              {user.phone ? (
                <span className="profile-chip">
                  <Phone size={13} /> {user.phone}
                </span>
              ) : null}
              <span className={`profile-chip profile-chip--role ${user.role === "admin" ? "is-admin" : ""}`}>
                <ShieldCheck size={13} /> {user.role === "admin" ? "Administrator" : "Guest"}
              </span>
            </div>
          </div>
        </div>
        <div className="profile-actions">
          {user.role === "admin" ? (
            <Link to="/admin" className="btn btn--ghost btn--sm">
              <Settings2 size={14} /> Control room
            </Link>
          ) : null}
          <button type="button" className="btn btn--ghost btn--sm" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>

      <div className="profile-stats">
        <Link to="/bookings" className="profile-stat">
          <span className="profile-stat-icon">
            <Ticket size={17} />
          </span>
          <div>
            {summary.loading ? <Skeleton style={{ width: 40, height: 26 }} /> : <strong>{stats.upcoming}</strong>}
            <span>Upcoming screenings</span>
          </div>
          <ArrowRight size={15} />
        </Link>
        <Link to="/bookings" className="profile-stat">
          <span className="profile-stat-icon">
            <CalendarDays size={17} />
          </span>
          <div>
            {summary.loading ? <Skeleton style={{ width: 40, height: 26 }} /> : <strong>{stats.total}</strong>}
            <span>Tickets in total</span>
          </div>
          <ArrowRight size={15} />
        </Link>
        <Link to="/notifications" className="profile-stat">
          <span className="profile-stat-icon">
            <Bell size={17} />
          </span>
          <div>
            {summary.loading ? <Skeleton style={{ width: 40, height: 26 }} /> : <strong>{stats.unread}</strong>}
            <span>Unread notifications</span>
          </div>
          <ArrowRight size={15} />
        </Link>
        <div className="profile-stat profile-stat--static">
          <span className="profile-stat-icon">
            <Sparkles size={17} />
          </span>
          <div>
            {summary.loading ? <Skeleton style={{ width: 70, height: 26 }} /> : <strong>{money(stats.spend)}</strong>}
            <span>Spent at Nocturne</span>
          </div>
        </div>
      </div>

      <div className="profile-layout">
        <section className="profile-card">
          <div className="profile-card-head">
            <div>
              <span className="eyebrow">Personal details</span>
              <h2>Keep it current</h2>
            </div>
            <UserRound size={19} />
          </div>
          <form className="profile-form" onSubmit={save}>
            {error ? (
              <div className="inline-banner inline-banner--error" role="alert">
                {error}
              </div>
            ) : null}
            <label className="field">
              <span>Full name</span>
              <input
                type="text"
                value={form.full_name}
                onChange={(event) => setForm((current) => ({ ...current, full_name: event.target.value }))}
                autoComplete="name"
              />
            </label>
            <label className="field">
              <span>Phone</span>
              <input
                type="tel"
                value={form.phone}
                onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))}
                placeholder="Add a phone number"
                autoComplete="tel"
              />
            </label>
            <label className="field field--readonly">
              <span>Email</span>
              <input type="email" value={user.email} readOnly />
              <small>Email changes are not available in this project.</small>
            </label>
            <div className="profile-form-actions">
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => setForm({ full_name: user.full_name, phone: user.phone || "" })}
                disabled={!dirty || saving}
              >
                Reset
              </button>
              <button type="submit" className="btn btn--gold btn--sm" disabled={!dirty || saving}>
                {saving ? <Spinner size={14} label="Saving" /> : <Check size={14} />} Save changes
              </button>
            </div>
          </form>
        </section>

        <aside className="profile-side">
          <div className="profile-side-card">
            <span className="profile-side-icon">
              <ShieldCheck size={18} />
            </span>
            <h3>Security, quietly handled</h3>
            <p>
              Passwords are hashed with bcrypt and every request is authorised through a signed JWT
              at the gateway. No password ever leaves this browser in clear text beyond sign-in.
            </p>
          </div>
          <div className="profile-side-card profile-side-card--links">
            <h3>Quick links</h3>
            <Link to="/bookings">
              <Ticket size={15} /> My bookings <ArrowRight size={13} />
            </Link>
            <Link to="/notifications">
              <Bell size={15} /> Notifications <ArrowRight size={13} />
            </Link>
            <Link to="/#now-showing">
              <CalendarDays size={15} /> Programme <ArrowRight size={13} />
            </Link>
            {user.role === "admin" ? (
              <Link to="/admin">
                <Settings2 size={15} /> Control room <ArrowRight size={13} />
              </Link>
            ) : null}
          </div>
          <div className="profile-side-card profile-side-card--muted">
            <h3>Need a hand?</h3>
            <p>
              The concierge can find a film, propose seats and hold them — payment stays with you.
            </p>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => window.dispatchEvent(new CustomEvent("nocturne:assistant-open"))}
            >
              <Sparkles size={14} /> Ask the concierge
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}
