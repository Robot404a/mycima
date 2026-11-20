import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  ClipboardCopy,
  Clock3,
  Download,
  Film,
  RefreshCw,
  Ticket,
  TicketCheck,
  TicketX,
  Wallet,
} from "lucide-react";
import { api } from "../../lib/api";
import { useApi, useDocumentTitle } from "../../lib/hooks";
import { formatDateLong, formatTime, money, relativeTime, seatList } from "../../lib/format";
import { ErrorState, PageLoader } from "../../components/Feedback";
import { Modal } from "../../components/Modal";
import {
  AdminEmpty,
  AdminPageHead,
  AdminSearch,
  MiniStat,
  StatusPill,
} from "./ui";
import { useToast } from "../../context/ToastContext";

function bookingCsv(bookings) {
  const lines = [
    ["Reference", "Status", "Film", "Starts at", "Seats", "Total", "Currency", "Created"].join(","),
    ...bookings.map((booking) => {
      const movie = booking.snapshot?.movie || {};
      return [
        booking.reference,
        booking.status,
        `"${(movie.title || "").replace(/"/g, '""')}"`,
        booking.starts_at,
        `"${seatList(booking.seats)}"`,
        booking.total_price,
        booking.currency,
        booking.created_at,
      ].join(",");
    }),
  ];
  return lines.join("\r\n");
}

function downloadCsv(bookings) {
  const blob = new Blob([bookingCsv(bookings)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `nocturne-bookings-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function DetailRow({ label, children }) {
  return (
    <div className="detail-row">
      <span>{label}</span>
      <strong>{children}</strong>
    </div>
  );
}

function BookingDetailModal({ booking, onClose }) {
  const { pushToast } = useToast();
  if (!booking) return null;
  const snapshot = booking.snapshot || {};
  const movie = snapshot.movie || {};
  const showtime = snapshot.showtime || {};
  const cinema = snapshot.cinema || {};
  const hall = snapshot.hall || {};
  return (
    <Modal
      open={Boolean(booking)}
      onClose={onClose}
      title={`Booking ${booking.reference}`}
      subtitle={`${movie.title} · ${seatList(booking.seats)}`}
      size="md"
      footer={
        <>
          <Link to={`/movies/${movie.id}`} className="btn btn--ghost btn--sm">
            <Film size={14} /> View film
          </Link>
          <button type="button" className="btn btn--gold btn--sm" onClick={onClose}>
            Close
          </button>
        </>
      }
    >
      <div className="admin-detail">
        <div className="admin-detail-head">
          <span className="detail-film">{movie.title}</span>
          <StatusPill status={booking.status} />
        </div>
        <div className="admin-detail-grid">
          <DetailRow label="Reference">
            <span className="mono">{booking.reference}</span>{" "}
            <button
              type="button"
              className="icon-btn icon-btn--inline"
              onClick={() => {
                navigator.clipboard?.writeText(booking.reference);
                pushToast("Reference copied.", "info");
              }}
              aria-label="Copy reference"
            >
              <ClipboardCopy size={13} />
            </button>
          </DetailRow>
          <DetailRow label="Date">{formatDateLong(showtime.starts_at || booking.starts_at)}</DetailRow>
          <DetailRow label="Time">{showtime.time || formatTime(showtime.starts_at)}</DetailRow>
          <DetailRow label="Cinema">{cinema.name}</DetailRow>
          <DetailRow label="Hall">{hall.name}</DetailRow>
          <DetailRow label="Seats">{seatList(booking.seats)}</DetailRow>
          <DetailRow label="Total">{money(booking.total_price, booking.currency)}</DetailRow>
          <DetailRow label="Payment">{booking.payment_transaction_id || "—"}</DetailRow>
          <DetailRow label="Created">{formatDateLong(booking.created_at)}</DetailRow>
          <DetailRow label="Refund">{booking.refund_status || "—"}</DetailRow>
          {booking.cancelled_at ? (
            <DetailRow label="Cancelled">{formatDateLong(booking.cancelled_at)}</DetailRow>
          ) : null}
        </div>
        <div className="admin-detail-seats">
          {(booking.seats || []).map((seat) => (
            <span key={seat.seat_id} className={`seat-chip seat-chip--${(seat.category || "regular").toLowerCase()}`}>
              {seat.seat_id}
              <small>{money(seat.price, booking.currency)}</small>
            </span>
          ))}
        </div>
      </div>
    </Modal>
  );
}

function HoldDetailModal({ hold, onClose }) {
  if (!hold) return null;
  const snapshot = hold.snapshot || {};
  const movie = snapshot.movie || {};
  const showtime = snapshot.showtime || {};
  return (
    <Modal
      open={Boolean(hold)}
      onClose={onClose}
      title="Seat hold"
      subtitle={`${movie.title || "Film"} · ${seatList(hold.seats)}`}
      size="md"
      footer={
        <button type="button" className="btn btn--gold btn--sm" onClick={onClose}>
          Close
        </button>
      }
    >
      <div className="admin-detail">
        <div className="admin-detail-head">
          <span className="detail-film">{movie.title}</span>
          <StatusPill status={hold.status} />
        </div>
        <div className="admin-detail-grid">
          <DetailRow label="Hold ID">
            <span className="mono">{hold.id}</span>
          </DetailRow>
          <DetailRow label="Starts">{formatDateLong(showtime.starts_at)}</DetailRow>
          <DetailRow label="Time">{showtime.time}</DetailRow>
          <DetailRow label="Cinema">{snapshot.cinema?.name}</DetailRow>
          <DetailRow label="Hall">{snapshot.hall?.name}</DetailRow>
          <DetailRow label="Seats">{seatList(hold.seats)}</DetailRow>
          <DetailRow label="Total">{money(hold.total_price, hold.currency)}</DetailRow>
          <DetailRow label="Expires">{formatDateLong(hold.expires_at)}</DetailRow>
          <DetailRow label="Created">{formatDateLong(hold.created_at)}</DetailRow>
        </div>
        <div className="admin-detail-seats">
          {(hold.seats || []).map((seat) => (
            <span key={seat.seat_id} className={`seat-chip seat-chip--${(seat.category || "regular").toLowerCase()}`}>
              {seat.seat_id}
              <small>{money(seat.price, hold.currency)}</small>
            </span>
          ))}
        </div>
      </div>
    </Modal>
  );
}

export default function AdminBookings() {
  useDocumentTitle("Bookings · Control room");
  const { pushToast } = useToast();
  const [tab, setTab] = useState("bookings");
  const [query, setQuery] = useState("");
  const [selectedBooking, setSelectedBooking] = useState(null);
  const [selectedHold, setSelectedHold] = useState(null);

  const loader = useCallback(async () => {
    const [bookings, holds] = await Promise.all([
      api("/admin/bookings", { params: { limit: 300 } }),
      api("/admin/holds", { params: { limit: 200 } }),
    ]);
    return { bookings: bookings.items || [], holds: holds.items || [] };
  }, []);
  const { data, error, loading, reload, refreshing } = useApi(loader, [], { interval: 30000 });

  const bookings = data?.bookings || [];
  const holds = data?.holds || [];

  const stats = useMemo(() => {
    const confirmed = bookings.filter((booking) => booking.status === "CONFIRMED");
    const cancelled = bookings.filter((booking) => booking.status === "CANCELLED");
    return {
      revenue: confirmed.reduce((sum, booking) => sum + Number(booking.total_price || 0), 0),
      confirmed: confirmed.length,
      cancelled: cancelled.length,
      activeHolds: holds.filter((hold) => hold.status === "ACTIVE").length,
    };
  }, [bookings, holds]);

  const filteredBookings = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return bookings;
    return bookings.filter((booking) => {
      const movie = booking.snapshot?.movie || {};
      return (
        booking.reference.toLowerCase().includes(needle) ||
        (movie.title || "").toLowerCase().includes(needle) ||
        (booking.snapshot?.cinema?.name || "").toLowerCase().includes(needle) ||
        seatList(booking.seats).toLowerCase().includes(needle)
      );
    });
  }, [bookings, query]);

  const filteredHolds = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return holds;
    return holds.filter((hold) => {
      const movie = hold.snapshot?.movie || {};
      return (
        hold.id.toLowerCase().includes(needle) ||
        (movie.title || "").toLowerCase().includes(needle) ||
        (hold.snapshot?.cinema?.name || "").toLowerCase().includes(needle) ||
        seatList(hold.seats).toLowerCase().includes(needle)
      );
    });
  }, [holds, query]);

  if (loading) return <PageLoader label="Counting tickets" />;
  if (error) return <ErrorState error={error} onRetry={() => reload(true)} title="Bookings are hiding" />;

  return (
    <div className="admin-page">
      <AdminPageHead
        eyebrow="Operations"
        title="Bookings & holds"
        description="Every confirmed ticket and every live seat hold across the platform."
        actions={
          <>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => downloadCsv(filteredBookings)}
              disabled={!filteredBookings.length}
            >
              <Download size={14} /> Export CSV
            </button>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => reload()}
              disabled={refreshing}
            >
              <RefreshCw size={14} className={refreshing ? "spin" : ""} /> Refresh
            </button>
          </>
        }
      />

      <div className="venue-stats">
        <MiniStat label="Simulated revenue" value={money(stats.revenue)} hint={`${stats.confirmed} paid`} />
        <MiniStat label="Confirmed" value={stats.confirmed} hint="Tickets in the system" />
        <MiniStat label="Cancelled" value={stats.cancelled} hint="With simulated refunds" />
        <MiniStat label="Active holds" value={stats.activeHolds} hint="Expire after 5 minutes" />
      </div>

      <div className="admin-toolbar">
        <div className="segmented" role="tablist" aria-label="Bookings or holds">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "bookings"}
            className={tab === "bookings" ? "is-active" : ""}
            onClick={() => setTab("bookings")}
          >
            <TicketCheck size={14} /> Bookings <span>{bookings.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "holds"}
            className={tab === "holds" ? "is-active" : ""}
            onClick={() => setTab("holds")}
          >
            <Clock3 size={14} /> Seat holds <span>{holds.length}</span>
          </button>
        </div>
        <AdminSearch
          value={query}
          onChange={setQuery}
          placeholder={tab === "bookings" ? "Reference, film, cinema or seat" : "Film, cinema or seat"}
        />
      </div>

      {tab === "bookings" ? (
        filteredBookings.length ? (
          <div className="admin-table-wrap">
            <table className="admin-table admin-table--bookings">
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Film &amp; screening</th>
                  <th>Venue</th>
                  <th>Seats</th>
                  <th>Total</th>
                  <th>Status</th>
                  <th>Booked</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filteredBookings.map((booking) => {
                  const movie = booking.snapshot?.movie || {};
                  const showtime = booking.snapshot?.showtime || {};
                  const cinema = booking.snapshot?.cinema || {};
                  return (
                    <tr key={booking.id} className="is-clickable" onClick={() => setSelectedBooking(booking)}>
                      <td>
                        <span className="mono">{booking.reference}</span>
                      </td>
                      <td>
                        <div className="table-title-cell">
                          <Film size={14} />
                          <span>
                            {movie.title}
                            <small>
                              {formatDateLong(showtime.starts_at || booking.starts_at)} ·{" "}
                              {showtime.time || formatTime(showtime.starts_at)}
                            </small>
                          </span>
                        </div>
                      </td>
                      <td>
                        {cinema.name}
                        <small className="table-sub">{booking.snapshot?.hall?.name}</small>
                      </td>
                      <td className="mono">{seatList(booking.seats)}</td>
                      <td>{money(booking.total_price, booking.currency)}</td>
                      <td>
                        <StatusPill status={booking.status} />
                      </td>
                      <td>{relativeTime(booking.created_at)}</td>
                      <td>
                        <button
                          type="button"
                          className="icon-btn"
                          aria-label="View booking"
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedBooking(booking);
                          }}
                        >
                          <ArrowRight size={15} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <AdminEmpty
            icon={TicketX}
            title="No bookings match"
            message="Change the search, or wait for the next guest to book."
          />
        )
      ) : filteredHolds.length ? (
        <div className="admin-table-wrap">
          <table className="admin-table admin-table--bookings">
            <thead>
              <tr>
                <th>Film</th>
                <th>Screening</th>
                <th>Seats</th>
                <th>Total</th>
                <th>Status</th>
                <th>Expires</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filteredHolds.map((hold) => {
                const movie = hold.snapshot?.movie || {};
                const showtime = hold.snapshot?.showtime || {};
                const active = hold.status === "ACTIVE";
                return (
                  <tr key={hold.id} className="is-clickable" onClick={() => setSelectedHold(hold)}>
                    <td>
                      <div className="table-title-cell">
                        <Ticket size={14} />
                        <span>{movie.title}</span>
                      </div>
                    </td>
                    <td>
                      {formatDateLong(showtime.starts_at || hold.created_at)}
                      <small className="table-sub">{showtime.time}</small>
                    </td>
                    <td className="mono">{seatList(hold.seats)}</td>
                    <td>{money(hold.total_price, hold.currency)}</td>
                    <td>
                      <StatusPill status={hold.status} />
                    </td>
                    <td>
                      {active ? (
                        <span className={hold.seconds_remaining < 60 ? "text-danger" : ""}>
                          {Math.max(0, Math.floor(hold.seconds_remaining / 60))}m{" "}
                          {Math.max(0, hold.seconds_remaining % 60)}s left
                        </span>
                      ) : (
                        formatTime(hold.expires_at)
                      )}
                    </td>
                    <td>{relativeTime(hold.created_at)}</td>
                    <td>
                      <button
                        type="button"
                        className="icon-btn"
                        aria-label="View hold"
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedHold(hold);
                        }}
                      >
                        <ArrowRight size={15} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <AdminEmpty icon={Wallet} title="No holds yet" message="Live seat holds will appear here the moment a guest reserves seats." />
      )}

      <div className="admin-note-row">
        <TicketCheck size={15} />
        <span>
          Holds expire automatically. The reservation service sweeps them every 15 seconds and
          publishes an event.
        </span>
        <span className="admin-note-price">
          {filteredBookings.length} bookings · {filteredHolds.length} holds
        </span>
      </div>

      <BookingDetailModal booking={selectedBooking} onClose={() => setSelectedBooking(null)} />
      <HoldDetailModal hold={selectedHold} onClose={() => setSelectedHold(null)} />
    </div>
  );
}
