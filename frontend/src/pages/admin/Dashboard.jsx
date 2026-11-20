import { useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  CalendarRange,
  Clapperboard,
  Clock3,
  Film,
  MonitorPlay,
  RefreshCw,
  Server,
  Sparkles,
  TicketCheck,
  TrendingUp,
  Users,
  Wallet,
} from "lucide-react";
import { api } from "../../lib/api";
import { hydrateAdminActivity } from "../../lib/booking";
import { useApi, useDocumentTitle } from "../../lib/hooks";
import { formatDateLong, formatTime, money, relativeTime, seatList } from "../../lib/format";
import { ErrorState, PageLoader } from "../../components/Feedback";
import {
  AdminPageHead,
  MiniStat,
  StatusPill,
} from "./ui";

function ServiceMesh({ items }) {
  if (!items?.length) {
    return <p className="admin-muted">Service health is unavailable right now.</p>;
  }
  return (
    <ul className="service-mesh">
      {items.map((service) => (
        <li key={service.service}>
          <span className={`service-dot ${service.up ? "is-up" : "is-down"}`} />
          <span className="service-name">{service.service}</span>
          <span className={`service-state ${service.up ? "is-up" : "is-down"}`}>
            {service.up ? "Operational" : "Unreachable"}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function AdminDashboard() {
  useDocumentTitle("Control room");
  const loader = useCallback(async () => {
    const [stats, bookings, holds, users, showtimes, upstreams] = await Promise.allSettled([
      api("/admin/stats"),
      api("/admin/bookings", { params: { limit: 6 } }),
      api("/admin/holds", { params: { limit: 6 } }),
      api("/admin/users", { params: { limit: 1 } }),
      api("/admin/showtimes", { params: { limit: 500 } }),
      api("/health/upstreams", { auth: false }),
    ]);
    const value = (result, fallback) => (result.status === "fulfilled" ? result.value : fallback);
    const bookingList = value(bookings, { bookings: [] });
    const holdList = value(holds, { holds: [] });
    const activity = await hydrateAdminActivity(
      bookingList.bookings || [],
      holdList.holds || [],
    );
    return {
      stats: value(stats, {}),
      bookings: { bookings: activity.bookings },
      holds: { holds: activity.holds },
      users: value(users, { total: 0 }),
      showtimes: value(showtimes, { items: [] }),
      upstreams: value(upstreams, { items: [] }),
    };
  }, []);
  const { data, error, loading, reload, refreshing } = useApi(loader, [], { interval: 45000 });

  const derived = useMemo(() => {
    const stats = data?.stats || {};
    const showtimes = data?.showtimes?.items || [];
    const confirmed = Number(stats.confirmed_bookings || 0);
    const cancelled = Number(stats.cancelled_bookings || 0);
    const total = confirmed + cancelled;
    const today = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Africa/Casablanca",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date());
    const todayShowtimes = showtimes.filter((item) => item.date === today && item.is_active);
    const activeShowtimes = showtimes.filter((item) => item.is_active).length;
    return {
      stats,
      confirmed,
      cancelled,
      cancellationRate: total ? Math.round((cancelled / total) * 100) : 0,
      todayShowtimes,
      activeShowtimes,
    };
  }, [data]);

  if (loading) return <PageLoader label="Opening the control room" />;
  if (error) {
    return <ErrorState error={error} title="The control room is offline" onRetry={() => reload(true)} />;
  }

  const { stats, confirmed, cancelled, cancellationRate, todayShowtimes, activeShowtimes } = derived;
  const bookings = data?.bookings?.bookings || [];
  const holds = data?.holds?.holds || [];
  const revenue = Number(stats.revenue || 0);
  const currency = stats.currency || "MAD";
  const totalBookings = confirmed + cancelled;
  const confirmedShare = totalBookings ? Math.round((confirmed / totalBookings) * 100) : 0;

  return (
    <div className="admin-page">
      <AdminPageHead
        eyebrow="Overview"
        title="The house, at a glance."
        description="Bookings, holds and service health across the MyCima platform."
        actions={
          <>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => reload()}
              disabled={refreshing}
            >
              <RefreshCw size={14} className={refreshing ? "spin" : ""} /> Refresh
            </button>
            <Link to="/admin/showtimes" className="btn btn--gold btn--sm">
              <CalendarRange size={14} /> New screening
            </Link>
          </>
        }
      />

      <div className="kpi-grid">
        <div className="kpi-card kpi-card--gold">
          <div className="kpi-head">
            <span className="kpi-icon">
              <Wallet size={18} />
            </span>
            <span className="kpi-trend">
              <TrendingUp size={13} /> Confirmed
            </span>
          </div>
          <span className="kpi-label">Simulated revenue</span>
          <strong className="kpi-value">{money(revenue, currency)}</strong>
          <span className="kpi-foot">{confirmed} paid bookings</span>
        </div>
        <div className="kpi-card">
          <div className="kpi-head">
            <span className="kpi-icon">
              <TicketCheck size={18} />
            </span>
          </div>
          <span className="kpi-label">Confirmed bookings</span>
          <strong className="kpi-value">{confirmed}</strong>
          <span className="kpi-foot">{stats.upcoming_bookings || 0} upcoming screenings</span>
        </div>
        <div className="kpi-card">
          <div className="kpi-head">
            <span className="kpi-icon">
              <Clock3 size={18} />
            </span>
          </div>
          <span className="kpi-label">Seats on hold</span>
          <strong className="kpi-value">{stats.active_holds || 0}</strong>
          <span className="kpi-foot">Expire automatically after 5 minutes</span>
        </div>
        <div className="kpi-card">
          <div className="kpi-head">
            <span className="kpi-icon">
              <Users size={18} />
            </span>
          </div>
          <span className="kpi-label">Registered guests</span>
          <strong className="kpi-value">{data?.users?.total || 0}</strong>
          <span className="kpi-foot">
            {stats.seats_booked ?? stats.seats_sold ?? 0} seats booked in total
          </span>
        </div>
      </div>

      <div className="admin-dash-grid">
        <section className="admin-card admin-card--wide">
          <div className="admin-card-head">
            <div>
              <span className="eyebrow">Operations</span>
              <h2>Service mesh</h2>
            </div>
            <span className="admin-live">
              <span className="pulse-dot" /> Polling every 45s
            </span>
          </div>
          <ServiceMesh items={data?.upstreams?.items} />
          <p className="admin-muted admin-card-note">
            The gateway verifies JWTs locally and proxies to each service. Reservation replicas are
            balanced round-robin through Docker DNS.
          </p>
        </section>

        <section className="admin-card">
          <div className="admin-card-head">
            <div>
              <span className="eyebrow">Bookings</span>
              <h2>Conversion</h2>
            </div>
          </div>
          <div className="booking-chart">
            <div
              className="donut"
              style={{
                background: `conic-gradient(var(--gold) 0 ${confirmedShare}%, rgba(255,255,255,0.08) ${confirmedShare}% 100%)`,
              }}
            >
              <div className="donut-hole">
                <strong>{confirmedShare}%</strong>
                <span>confirmed</span>
              </div>
            </div>
            <div className="donut-legend">
              <div>
                <span className="legend-dot legend-dot--gold" /> Confirmed <strong>{confirmed}</strong>
              </div>
              <div>
                <span className="legend-dot legend-dot--muted" /> Cancelled <strong>{cancelled}</strong>
              </div>
              <div>
                <span className="legend-dot legend-dot--line" /> Cancellation rate{" "}
                <strong>{cancellationRate}%</strong>
              </div>
            </div>
          </div>
        </section>

        <section className="admin-card">
          <div className="admin-card-head">
            <div>
              <span className="eyebrow">Programme</span>
              <h2>Today &amp; ahead</h2>
            </div>
          </div>
          <div className="mini-stat-grid">
            <MiniStat label="Screenings today" value={todayShowtimes.length} hint="Africa/Casablanca" />
            <MiniStat label="Active screenings" value={activeShowtimes} hint="Published to the site" />
            <MiniStat
              label="Seats booked"
              value={stats.seats_booked ?? stats.seats_sold ?? 0}
              hint="Across all active screenings"
            />
          </div>
          {todayShowtimes.length ? (
            <div className="today-screenings">
              {todayShowtimes.slice(0, 4).map((item) => (
                <div key={item.id} className="today-screening">
                  <span>{item.time}</span>
                  <div>
                    <strong>{item.movie_title}</strong>
                    <small>
                      {item.cinema?.name} · {item.hall?.name} · {item.format_label}
                    </small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="admin-muted">No screenings scheduled for today.</p>
          )}
        </section>
      </div>

      <div className="admin-dash-grid admin-dash-grid--tables">
        <section className="admin-card admin-card--wide">
          <div className="admin-card-head">
            <div>
              <span className="eyebrow">Latest</span>
              <h2>Recent bookings</h2>
            </div>
            <Link to="/admin/bookings" className="text-btn">
              All bookings <ArrowRight size={12} />
            </Link>
          </div>
          {bookings.length ? (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Reference</th>
                    <th>Film</th>
                    <th>Seats</th>
                    <th>Total</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {bookings.map((booking) => {
                    const movie = booking.snapshot?.movie || {};
                    const showtime = booking.snapshot?.showtime || {};
                    return (
                      <tr key={booking.id}>
                        <td>
                          <span className="mono">{booking.reference}</span>
                          <small className="table-sub">{relativeTime(booking.created_at)}</small>
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
                        <td className="mono">{seatList(booking.seats)}</td>
                        <td>{money(booking.total_price, booking.currency)}</td>
                        <td>
                          <StatusPill status={booking.status} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="admin-muted">No bookings yet.</p>
          )}
        </section>

        <section className="admin-card">
          <div className="admin-card-head">
            <div>
              <span className="eyebrow">Right now</span>
              <h2>Active holds</h2>
            </div>
          </div>
          {holds.filter((hold) => hold.status === "ACTIVE").length ? (
            <ul className="admin-hold-list">
              {holds
                .filter((hold) => hold.status === "ACTIVE")
                .slice(0, 5)
                .map((hold) => (
                  <li key={hold.id}>
                    <span className="admin-hold-seats">{seatList(hold.seats)}</span>
                    <div>
                      <strong>{hold.snapshot?.movie?.title || "Film"}</strong>
                      <small>
                        {hold.snapshot?.cinema?.name} · {money(hold.total_price, hold.currency)}
                      </small>
                    </div>
                    <span className={`hold-clock ${hold.seconds_remaining < 60 ? "is-urgent" : ""}`}>
                      {Math.max(0, Math.floor(hold.seconds_remaining / 60))}m
                    </span>
                  </li>
                ))}
            </ul>
          ) : (
            <p className="admin-muted">No active holds. The room is calm.</p>
          )}
          <div className="admin-quick-actions">
            <Link to="/admin/movies">
              <Clapperboard size={15} /> Manage films <ArrowRight size={12} />
            </Link>
            <Link to="/admin/halls">
              <MonitorPlay size={15} /> Hall layout <ArrowRight size={12} />
            </Link>
            <Link to="/admin/users">
              <Sparkles size={15} /> Guests <ArrowRight size={12} />
            </Link>
          </div>
        </section>
      </div>

      <div className="admin-footnote">
        <Activity size={15} /> Distributed cinema platform · {confirmed} confirmed · {cancelled}{" "}
        cancelled · {activeShowtimes} live screenings
        <Server size={15} />
      </div>
    </div>
  );
}
