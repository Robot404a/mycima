import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  CalendarDays,
  Clock3,
  Film,
  MapPin,
  Search,
  Ticket,
  TicketCheck,
} from "lucide-react";
import { api } from "../lib/api";
import { useApi, useDocumentTitle } from "../lib/hooks";
import { formatDateLong, formatTime, money, seatList } from "../lib/format";
import { EmptyState, ErrorState, PageLoader, Poster, Skeleton } from "../components/Feedback";

function BookingRow({ booking }) {
  const snapshot = booking.snapshot || {};
  const movie = snapshot.movie || {};
  const showtime = snapshot.showtime || {};
  const cinema = snapshot.cinema || {};
  const hall = snapshot.hall || {};
  const cancelled = booking.status === "CANCELLED";
  const past = new Date(booking.starts_at).getTime() < Date.now();

  return (
    <article className={`booking-row ${cancelled ? "is-cancelled" : ""} ${past ? "is-past" : ""}`}>
      <Link to={`/bookings/${booking.id}`} className="booking-row-poster">
        <Poster src={movie.poster_url} title={movie.title} />
        <span className={`booking-row-stamp booking-row-stamp--${booking.status.toLowerCase()}`}>
          {cancelled ? "Cancelled" : past ? "Seen" : "Confirmed"}
        </span>
      </Link>
      <div className="booking-row-body">
        <div className="booking-row-head">
          <div>
            <span className="eyebrow">{showtime.format_label || showtime.format} · {showtime.language}</span>
            <h2>{movie.title}</h2>
          </div>
          <span className="booking-row-ref">{booking.reference}</span>
        </div>
        <div className="booking-row-meta">
          <span>
            <CalendarDays size={14} /> {formatDateLong(showtime.starts_at || booking.starts_at)}
          </span>
          <span>
            <Clock3 size={14} /> {showtime.time || formatTime(showtime.starts_at)}
          </span>
          <span>
            <MapPin size={14} /> {cinema.name} · {hall.name}
          </span>
        </div>
        <div className="booking-row-seats">
          <span>
            <Ticket size={14} /> {seatList(booking.seats)}
          </span>
          <span className="booking-row-total">{money(booking.total_price, booking.currency)}</span>
        </div>
        <div className="booking-row-actions">
          <Link to={`/bookings/${booking.id}`} className="btn btn--ghost btn--xs">
            {cancelled ? "View details" : "View ticket"} <ArrowRight size={13} />
          </Link>
          {cancelled ? (
            <Link to={`/movies/${movie.id}`} className="text-btn">
              Book again <ArrowRight size={12} />
            </Link>
          ) : booking.can_cancel ? (
            <span className="booking-row-hint">Cancel up to 2 h before</span>
          ) : null}
        </div>
      </div>
    </article>
  );
}

export default function Bookings() {
  useDocumentTitle("My bookings");
  const [tab, setTab] = useState("upcoming");
  const [query, setQuery] = useState("");

  const loader = useCallback(() => api("/bookings/me"), []);
  const { data, error, loading, reload } = useApi(loader, []);

  const items = data?.items || [];
  const now = Date.now();
  const upcoming = useMemo(
    () =>
      items
        .filter((booking) => booking.status === "CONFIRMED" && new Date(booking.starts_at).getTime() >= now)
        .sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at)),
    [items, now],
  );
  const history = useMemo(
    () =>
      items
        .filter((booking) => !(booking.status === "CONFIRMED" && new Date(booking.starts_at).getTime() >= now))
        .sort((a, b) => new Date(b.starts_at) - new Date(a.starts_at)),
    [items, now],
  );

  const current = tab === "upcoming" ? upcoming : history;
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return current;
    return current.filter((booking) => {
      const movie = booking.snapshot?.movie || {};
      return (
        (movie.title || "").toLowerCase().includes(needle) ||
        booking.reference.toLowerCase().includes(needle) ||
        (booking.snapshot?.cinema?.name || "").toLowerCase().includes(needle)
      );
    });
  }, [current, query]);

  if (loading) return <PageLoader label="Collecting your tickets" />;

  return (
    <div className="bookings-page page">
      <header className="bookings-head">
        <div>
          <span className="eyebrow">Your private screening room</span>
          <h1>My <em>bookings</em></h1>
          <p>Every ticket, every seat, kept in one quiet place.</p>
        </div>
        <div className="bookings-stats">
          <div>
            <span>Upcoming</span>
            <strong>{upcoming.length}</strong>
          </div>
          <div>
            <span>All tickets</span>
            <strong>{items.length}</strong>
          </div>
          <div>
            <span>Spent</span>
            <strong>
              {money(
                items.reduce((sum, booking) => sum + Number(booking.total_price || 0), 0),
                "MAD",
              )}
            </strong>
          </div>
        </div>
      </header>

      {error ? (
        <ErrorState error={error} title="Your tickets are hiding" onRetry={() => reload(true)} />
      ) : (
        <>
          <div className="bookings-toolbar">
            <div className="segmented" role="tablist" aria-label="Booking filters">
              <button
                type="button"
                role="tab"
                aria-selected={tab === "upcoming"}
                className={tab === "upcoming" ? "is-active" : ""}
                onClick={() => setTab("upcoming")}
              >
                Upcoming <span>{upcoming.length}</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={tab === "history"}
                className={tab === "history" ? "is-active" : ""}
                onClick={() => setTab("history")}
              >
                Past & cancelled <span>{history.length}</span>
              </button>
            </div>
            <label className="search-field search-field--sm">
              <Search size={15} />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Film, venue or reference"
                aria-label="Search bookings"
              />
            </label>
          </div>

          {filtered.length ? (
            <div className="booking-list">
              {filtered.map((booking) => (
                <BookingRow key={booking.id} booking={booking} />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={tab === "upcoming" ? TicketCheck : Film}
              title={
                query
                  ? "No tickets match that"
                  : tab === "upcoming"
                    ? "Your next evening is wide open"
                    : "Nothing in the archive yet"
              }
              message={
                query
                  ? "Try a different film, venue or reference."
                  : tab === "upcoming"
                    ? "Choose a film, pick a screening and reserve the seats you want. They will appear here."
                    : "Past and cancelled bookings will collect here."
              }
              action={
                query ? (
                  <button type="button" className="btn btn--ghost btn--sm" onClick={() => setQuery("")}>
                    Clear search
                  </button>
                ) : (
                  <Link to="/#now-showing" className="btn btn--gold btn--sm">
                    <Film size={14} /> Explore the programme
                  </Link>
                )
              }
            />
          )}

          {tab === "upcoming" && upcoming.length ? (
            <div className="bookings-extra">
              <Skeleton className="bookings-extra-poster" />
              <div>
                <span className="eyebrow">A small ritual</span>
                <h3>Make an evening of it.</h3>
                <p>
                  The bar opens an hour before the first screening. Ask the concierge for a film
                  that fits the mood, or browse what's new this week.
                </p>
                <Link to="/#now-showing" className="btn btn--ghost btn--sm">
                  Find another film <ArrowRight size={14} />
                </Link>
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
