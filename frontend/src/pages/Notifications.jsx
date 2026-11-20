import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Bell,
  BellOff,
  CheckCheck,
  Clock3,
  CreditCard,
  Ticket,
  TicketCheck,
  Trash2,
  TriangleAlert,
  XCircle,
} from "lucide-react";
import { api, apiErrorMessage } from "../lib/api";
import { useApi, useDocumentTitle } from "../lib/hooks";
import { formatDateLong, formatTime, relativeTime } from "../lib/format";
import { EmptyState, ErrorState, PageLoader, Spinner } from "../components/Feedback";
import { useToast } from "../context/ToastContext";

const ICONS = {
  "booking.confirmed": TicketCheck,
  "booking.cancelled": XCircle,
  "payment.failed": CreditCard,
  "hold.expired": Clock3,
  "hold.cancelled": BellOff,
  "seats.held": Clock3,
};

function notificationLink(item) {
  const data = item.data || {};
  if (data.booking_id) return `/bookings/${data.booking_id}`;
  if (item.event_type === "seats.held" && data.hold_id) return `/checkout/${data.hold_id}`;
  return null;
}

function NotificationItem({ item, onRead, onDelete, busy }) {
  const Icon = ICONS[item.event_type] || Bell;
  const link = notificationLink(item);
  const when = new Date(item.created_at);
  return (
    <article className={`notification-item ${item.is_read ? "is-read" : "is-unread"}`}>
      <span className={`notification-icon notification-icon--${item.event_type.split(".")[0]}`}>
        <Icon size={17} />
      </span>
      <div className="notification-body">
        <div className="notification-top">
          <h3>{item.title}</h3>
          <time dateTime={item.created_at} title={`${formatDateLong(when)} · ${formatTime(when)}`}>
            {relativeTime(item.created_at)}
          </time>
        </div>
        <p>{item.message}</p>
        <div className="notification-meta">
          <span>{formatDateLong(when)} · {formatTime(when)}</span>
          <div className="notification-actions">
            {link ? (
              <Link to={link} className="text-btn">
                View <ArrowRight size={12} />
              </Link>
            ) : null}
            {!item.is_read ? (
              <button type="button" className="text-btn" onClick={() => onRead(item)} disabled={busy}>
                Mark read
              </button>
            ) : null}
            <button
              type="button"
              className="icon-btn icon-btn--danger"
              onClick={() => onDelete(item)}
              disabled={busy}
              aria-label={`Delete notification: ${item.title}`}
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      </div>
      {!item.is_read ? <span className="notification-unread-dot" aria-label="Unread" /> : null}
    </article>
  );
}

export default function Notifications() {
  useDocumentTitle("Notifications");
  const { pushToast } = useToast();
  const [tab, setTab] = useState("all");
  const [busy, setBusy] = useState(false);

  const loader = useCallback(
    () => api("/notifications/me", { params: { limit: 100, unread_only: tab === "unread" } }),
    [tab],
  );
  const { data, error, loading, reload, setData } = useApi(loader, [tab]);

  const items = data?.items || [];
  const unread = data?.unread || 0;
  const filtered = useMemo(() => items, [items]);

  const markRead = async (item) => {
    setBusy(true);
    const previous = data;
    setData((current) =>
      current
        ? {
            ...current,
            unread: Math.max(0, current.unread - (item.is_read ? 0 : 1)),
            items: current.items.map((entry) =>
              entry.id === item.id
                ? { ...entry, is_read: true, read_at: new Date().toISOString() }
                : entry,
            ),
          }
        : current,
    );
    try {
      await api(`/notifications/${item.id}/read`, { method: "PATCH" });
    } catch (err) {
      setData(previous);
      pushToast(apiErrorMessage(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const markAll = async () => {
    setBusy(true);
    try {
      await api("/notifications/read-all", { method: "POST" });
      pushToast("All notifications marked as read.", "success");
      reload();
    } catch (err) {
      pushToast(apiErrorMessage(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (item) => {
    setBusy(true);
    const previous = data;
    setData((current) =>
      current
        ? {
            ...current,
            total: Math.max(0, current.total - 1),
            unread: Math.max(0, current.unread - (item.is_read ? 0 : 1)),
            items: current.items.filter((entry) => entry.id !== item.id),
          }
        : current,
    );
    try {
      await api(`/notifications/${item.id}`, { method: "DELETE" });
    } catch (err) {
      setData(previous);
      pushToast(apiErrorMessage(err), "error");
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <PageLoader label="Catching up" />;

  return (
    <div className="notifications-page page">
      <header className="notifications-head">
        <div>
          <span className="eyebrow">From the house</span>
          <h1>Notifications</h1>
          <p>Holds, bookings, refunds and the small updates that keep an evening moving.</p>
        </div>
        {unread > 0 ? (
          <button type="button" className="btn btn--ghost btn--sm" onClick={markAll} disabled={busy}>
            <CheckCheck size={14} /> Mark all read
          </button>
        ) : null}
      </header>

      {error ? (
        <ErrorState error={error} title="Your notifications are hiding" onRetry={() => reload(true)} />
      ) : (
        <>
          <div className="notifications-toolbar">
            <div className="segmented" role="tablist" aria-label="Notification filters">
              <button
                type="button"
                role="tab"
                aria-selected={tab === "all"}
                className={tab === "all" ? "is-active" : ""}
                onClick={() => setTab("all")}
              >
                All
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={tab === "unread"}
                className={tab === "unread" ? "is-active" : ""}
                onClick={() => setTab("unread")}
              >
                Unread <span>{unread}</span>
              </button>
            </div>
            <span className="notifications-count">
              {filtered.length} notification{filtered.length === 1 ? "" : "s"}
            </span>
          </div>

          {filtered.length ? (
            <div className="notification-list">
              {filtered.map((item) => (
                <NotificationItem
                  key={item.id}
                  item={item}
                  onRead={markRead}
                  onDelete={remove}
                  busy={busy}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={tab === "unread" ? BellOff : Bell}
              title={tab === "unread" ? "Nothing unread" : "Your inbox is quiet"}
              message={
                tab === "unread"
                  ? "You're all caught up. New holds and booking updates will appear here."
                  : "Book a screening and the house will write to you here."
              }
              action={
                tab === "unread" ? (
                  <button type="button" className="btn btn--ghost btn--sm" onClick={() => setTab("all")}>
                    View all
                  </button>
                ) : (
                  <Link to="/#now-showing" className="btn btn--gold btn--sm">
                    <Ticket size={14} /> Find a film
                  </Link>
                )
              }
            />
          )}

          <div className="notifications-note">
            <TriangleAlert size={15} />
            <p>
              Emails are rendered and stored by the notification service. If the mail server is
              unavailable, failed messages are retried automatically and never block a booking.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
