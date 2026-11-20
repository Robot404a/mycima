import { useCallback, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  CalendarPlus,
  CheckCircle2,
  Clock3,
  MapPin,
  Printer,
  RotateCcw,
  Ticket,
  TriangleAlert,
  XCircle,
} from "lucide-react";
import { api, apiErrorMessage } from "../lib/api";
import { useApi, useDocumentTitle } from "../lib/hooks";
import {
  duration as formatDuration,
  formatDateLong,
  formatTime,
  money,
  seatList,
} from "../lib/format";
import { ErrorState, PageLoader, Poster, Spinner } from "../components/Feedback";
import { fetchShowtime, normalizeBooking } from "../lib/booking";
import { Modal } from "../components/Modal";
import { useToast } from "../context/ToastContext";

function hashString(value) {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function TicketCode({ value, size = 29 }) {
  const cells = useMemo(() => {
    const seed = hashString(value || "mycima");
    let state = seed || 1;
    const next = () => {
      state ^= state << 13;
      state ^= state >>> 17;
      state ^= state << 5;
      return (state >>> 0) / 4294967296;
    };
    const grid = [];
    for (let y = 0; y < size; y += 1) {
      for (let x = 0; x < size; x += 1) {
        const finder = (cx, cy) => {
          const dx = x - cx;
          const dy = y - cy;
          if (dx < 0 || dy < 0 || dx > 6 || dy > 6) return null;
          const border = dx === 0 || dy === 0 || dx === 6 || dy === 6;
          const core = dx >= 2 && dx <= 4 && dy >= 2 && dy <= 4;
          return border || core;
        };
        const topLeft = finder(1, 1);
        const topRight = finder(size - 8, 1);
        const bottomLeft = finder(1, size - 8);
        let filled;
        if (topLeft !== null) filled = topLeft;
        else if (topRight !== null) filled = topRight;
        else if (bottomLeft !== null) filled = bottomLeft;
        else filled = next() > 0.53;
        if (filled) grid.push([x, y]);
      }
    }
    return grid;
  }, [value, size]);

  return (
    <svg
      viewBox={`0 0 ${size + 2} ${size + 2}`}
      className="ticket-qr"
      role="img"
      aria-label={`Ticket code ${value}`}
    >
      <rect width={size + 2} height={size + 2} fill="#f4efe3" rx="1.4" />
      {cells.map(([x, y]) => (
        <rect key={`${x}-${y}`} x={x + 1} y={y + 1} width="1" height="1" fill="#0b0c10" />
      ))}
    </svg>
  );
}

function icsDate(date) {
  return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function downloadCalendar(booking) {
  const snapshot = booking.snapshot || {};
  const movie = snapshot.movie || {};
  const showtime = snapshot.showtime || {};
  const cinema = snapshot.cinema || {};
  const hall = snapshot.hall || {};
  const start = new Date(showtime.starts_at || booking.starts_at);
  const end = new Date(start.getTime() + (movie.duration_min || 120) * 60000);
  const seats = seatList(booking.seats);
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//MyCima//Cinema Booking//EN",
    "BEGIN:VEVENT",
    `UID:${booking.id}@mycima.ma`,
    `DTSTAMP:${icsDate(new Date())}`,
    `DTSTART:${icsDate(start)}`,
    `DTEND:${icsDate(end)}`,
    `SUMMARY:${movie.title || "MyCima film"}`,
    `LOCATION:${[cinema.name, hall.name, cinema.address].filter(Boolean).join(", ").replace(/,/g, "\\,")}`,
    `DESCRIPTION:${`Seats ${seats}. Booking ${booking.reference}. ${movie.title || ""}`.replace(/,/g, "\\,")}`,
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  const blob = new Blob([lines.join("\r\n")], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `mycima-${booking.reference}.ics`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export default function BookingDetail() {
  const { bookingId } = useParams();
  const [searchParams] = useSearchParams();
  const { pushToast } = useToast();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const isNew = searchParams.get("new") === "1";

  const loader = useCallback(async () => {
    const booking = await api(`/bookings/${bookingId}`);
    const showtime = await fetchShowtime(booking.showtime_id);
    const normalized = normalizeBooking(booking, showtime);
    // The showtime only carries a movie brief; the ticket wants the full film card.
    if (showtime?.movie?.id) {
      try {
        const movie = await api(`/movies/${showtime.movie.id}`, { auth: false });
        normalized.snapshot = { ...normalized.snapshot, movie: { ...normalized.snapshot.movie, ...movie } };
      } catch {
        /* keep the brief */
      }
    }
    return normalized;
  }, [bookingId]);
  const { data: booking, error, loading, reload } = useApi(loader, [bookingId]);
  useDocumentTitle(booking ? `Ticket ${booking.reference}` : "Your ticket");

  const snapshot = booking?.snapshot || {};
  const movie = snapshot.movie || {};
  const showtime = snapshot.showtime || {};
  const cinema = snapshot.cinema || {};
  const hall = snapshot.hall || {};
  const cancelled = booking?.status === "CANCELLED";

  const cancelBooking = async () => {
    setCancelling(true);
    try {
      await api(`/bookings/${bookingId}/cancel`, { method: "POST" });
      pushToast("Booking cancelled. A simulated refund has been issued.", "success");
      setCancelOpen(false);
      reload();
    } catch (err) {
      pushToast(apiErrorMessage(err), "error");
    } finally {
      setCancelling(false);
    }
  };

  if (loading) return <PageLoader label="Printing your ticket" />;
  if (error) {
    return (
      <div className="page page--narrow">
        <ErrorState error={error} title="Ticket not found" onRetry={() => reload(true)} />
        <div className="center-actions">
          <Link to="/bookings" className="btn btn--ghost btn--sm">
            <ArrowLeft size={14} /> My bookings
          </Link>
        </div>
      </div>
    );
  }
  if (!booking) return null;

  return (
    <div className="ticket-page page">
      <div className="booking-topbar">
        <Link to="/bookings" className="back-link">
          <ArrowLeft size={15} /> My bookings
        </Link>
        <span className={`status-pill status-pill--${booking.status.toLowerCase()}`}>
          {booking.status === "CONFIRMED" ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
          {booking.status === "CONFIRMED" ? "Confirmed" : "Cancelled"}
        </span>
      </div>

      {isNew && !cancelled ? (
        <div className="booking-success">
          <div className="booking-success-glow" aria-hidden="true" />
          <span className="booking-success-icon">
            <CheckCircle2 size={26} />
          </span>
          <div>
            <span className="eyebrow">Payment approved</span>
            <h1>Your seats are waiting.</h1>
            <p>
              A confirmation was sent to your notifications. Show the code below at the door — the
              room opens twenty minutes before the film.
            </p>
          </div>
        </div>
      ) : null}

      <div className={`ticket-wrap ${cancelled ? "is-cancelled" : ""}`}>
        <article className="cinema-ticket" aria-label={`Ticket ${booking.reference}`}>
          <div className="ticket-main">
            <div className="ticket-topline">
              <span className="brand-word">
                MYCIMA
                <small>Cinema, after dark</small>
              </span>
              <span className="ticket-admit">Admit {booking.seats?.length || 1}</span>
            </div>

            <div className="ticket-film">
              <div className="ticket-poster">
                <Poster src={movie.poster_url} title={movie.title} />
              </div>
              <div className="ticket-film-copy">
                <span className="eyebrow">{showtime.format_label || showtime.format}</span>
                <h2>{movie.title}</h2>
                <p className="ticket-tagline">{movie.tagline}</p>
                <div className="ticket-film-meta">
                  <span>{formatDuration(movie.duration_min)}</span>
                  <span className="dot" />
                  <span>{showtime.language}</span>
                  <span className="dot" />
                  <span className="age-chip">{movie.age_rating}</span>
                </div>
              </div>
            </div>

            <div className="ticket-grid">
              <div>
                <span className="ticket-label">Date</span>
                <strong>{formatDateLong(showtime.starts_at || booking.starts_at)}</strong>
              </div>
              <div>
                <span className="ticket-label">Time</span>
                <strong>{showtime.time || formatTime(showtime.starts_at)}</strong>
              </div>
              <div>
                <span className="ticket-label">Cinema</span>
                <strong>
                  <MapPin size={13} /> {cinema.name}
                </strong>
                <small>{cinema.address}</small>
              </div>
              <div>
                <span className="ticket-label">Hall</span>
                <strong>{hall.name}</strong>
                <small>{hall.screen_type}</small>
              </div>
              <div>
                <span className="ticket-label">Seats</span>
                <strong className="ticket-seats">{seatList(booking.seats)}</strong>
              </div>
              <div>
                <span className="ticket-label">Total</span>
                <strong>{money(booking.total_price, booking.currency)}</strong>
              </div>
            </div>

            <div className="ticket-foot">
              <span>
                <Ticket size={14} /> Reference <strong>{booking.reference}</strong>
              </span>
              <span>
                <CalendarDays size={14} /> Booked {formatDateLong(booking.created_at)}
              </span>
            </div>
          </div>

          <div className="ticket-stub">
            <div className="ticket-stub-punches" aria-hidden="true" />
            <div className="ticket-stub-inner">
              <TicketCode value={booking.reference} />
              <span className="ticket-stub-ref">{booking.reference}</span>
              <span className="ticket-stub-hint">Scan at the door</span>
              <span className={`ticket-stub-status ${cancelled ? "is-cancelled" : ""}`}>
                {cancelled ? "Cancelled" : "Confirmed"}
              </span>
            </div>
          </div>
        </article>

        <div className="ticket-actions">
          {!cancelled ? (
            <>
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => window.print()}>
                <Printer size={14} /> Print ticket
              </button>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => downloadCalendar(booking)}
              >
                <CalendarPlus size={14} /> Add to calendar
              </button>
            </>
          ) : null}
          <Link to={`/movies/${movie.id}`} className="btn btn--gold btn--sm">
            Book this film again <ArrowRight size={14} />
          </Link>
        </div>
      </div>

      <div className="ticket-lower">
        <div className="ticket-notes">
          <h3>Before the screening</h3>
          <ul>
            <li>
              <Clock3 size={15} /> Doors open 20 minutes before the film. Latecomers are seated at
              the house's discretion.
            </li>
            <li>
              <Ticket size={15} /> Present this ticket code at the entrance. Every guest needs their
              own seat.
            </li>
            <li>
              <MapPin size={15} /> {cinema.name}, {cinema.address}. Arrive early for the bar.
            </li>
          </ul>
        </div>

        <div className="ticket-policy">
          <h3>Booking details</h3>
          <dl>
            <div>
              <dt>Payment</dt>
              <dd>{booking.payment_transaction_id || "—"}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{booking.status}</dd>
            </div>
            <div>
              <dt>Refund</dt>
              <dd>{booking.refund_status || "Not applicable"}</dd>
            </div>
            {booking.cancelled_at ? (
              <div>
                <dt>Cancelled</dt>
                <dd>{formatDateLong(booking.cancelled_at)}</dd>
              </div>
            ) : null}
          </dl>
          {booking.status === "CONFIRMED" ? (
            booking.can_cancel ? (
              <div className="ticket-cancel">
                <p>
                  Changed your mind? You can cancel until two hours before the screening for a
                  simulated refund.
                </p>
                <button
                  type="button"
                  className="btn btn--danger btn--sm"
                  onClick={() => setCancelOpen(true)}
                >
                  <RotateCcw size={14} /> Cancel booking
                </button>
              </div>
            ) : (
              <p className="ticket-cancel-note">
                <TriangleAlert size={14} /> This booking can no longer be cancelled online — the
                two-hour cutoff has passed.
              </p>
            )
          ) : (
            <p className="ticket-cancel-note">
              <CheckCircle2 size={14} /> A simulated refund was issued to the original card.
            </p>
          )}
        </div>
      </div>

      <Modal
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        title="Cancel this booking?"
        subtitle={`${movie.title} · ${seatList(booking.seats)}`}
        size="sm"
        footer={
          <>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setCancelOpen(false)}>
              Keep booking
            </button>
            <button
              type="button"
              className="btn btn--danger btn--sm"
              onClick={cancelBooking}
              disabled={cancelling}
            >
              {cancelling ? <Spinner size={14} label="Cancelling" /> : null} Cancel booking
            </button>
          </>
        }
      >
        <p className="modal-copy">
          The seats return to the room and a simulated refund of{" "}
          <strong>{money(booking.total_price, booking.currency)}</strong> is issued. This cannot be
          undone.
        </p>
      </Modal>
    </div>
  );
}
