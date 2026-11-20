import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Armchair,
  ArrowLeft,
  ArrowRight,
  Box,
  Check,
  Clock3,
  LayoutGrid,
  MapPin,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Ticket,
  TriangleAlert,
} from "lucide-react";
import { api, apiErrorMessage } from "../lib/api";
import { useApi, useDocumentTitle, useMediaQuery } from "../lib/hooks";
import { formatDateLong, money } from "../lib/format";
import { PageLoader, ErrorState, Spinner, EmptyState } from "../components/Feedback";
import { StepIndicator } from "../components/StepIndicator";
import { Countdown } from "../components/Countdown";
import { SeatPlan2D } from "../components/SeatPlan2D";
import { SeatMap3D } from "../components/SeatMap3D";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";

const STEPS = ["Screening", "Seats", "Payment", "Ticket"];
const MAX_SEATS = 8;

function supportsWebGL() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(
      window.WebGLRenderingContext &&
        (canvas.getContext("webgl") || canvas.getContext("experimental-webgl")),
    );
  } catch {
    return false;
  }
}

function VenueLine({ data }) {
  if (!data) return null;
  return (
    <div className="booking-venue">
      <span>
        <MapPin size={14} /> {data.cinema?.name}
      </span>
      <span className="dot" />
      <span>{data.hall?.name}</span>
      <span className="dot" />
      <span>{data.hall?.screen_type}</span>
    </div>
  );
}

function Legend() {
  return (
    <div className="seat-legend" aria-label="Seat legend">
      <span>
        <i className="seat-key seat-key--available" /> Available
      </span>
      <span>
        <i className="seat-key seat-key--selected" /> Selected
      </span>
      <span>
        <i className="seat-key seat-key--held" /> On hold
      </span>
      <span>
        <i className="seat-key seat-key--booked" /> Booked
      </span>
      <span>
        <i className="seat-key seat-key--vip" /> VIP
      </span>
    </div>
  );
}

function ExistingHolds({ holds }) {
  if (!holds?.length) return null;
  return (
    <div className="existing-holds">
      {holds.map((hold) => (
        <div key={hold.id} className="existing-hold">
          <span className="existing-hold-icon">
            <Ticket size={15} />
          </span>
          <div>
            <strong>You already have seats on hold</strong>
            <p>
              {money(hold.total_price)} · <Countdown expiresAt={hold.expires_at} compact label="" />
            </p>
          </div>
          <Link to={`/checkout/${hold.id}`} className="btn btn--gold btn--xs">
            Resume <ArrowRight size={13} />
          </Link>
        </div>
      ))}
    </div>
  );
}

export default function SeatSelection() {
  const { showtimeId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { pushToast } = useToast();
  const { isAuthenticated } = useAuth();
  const isMobile = useMediaQuery("(max-width: 900px)");
  const canUse3D = useMemo(() => supportsWebGL(), []);
  const [view, setView] = useState("2d");
  const [selected, setSelected] = useState(() => new Set());
  const [holding, setHolding] = useState(false);
  const [holdError, setHoldError] = useState(null);
  const [hovered, setHovered] = useState(null);
  const [notice, setNotice] = useState("");

  const loader = useCallback(
    () => api(`/showtimes/${showtimeId}/seats`, { auth: isAuthenticated }),
    [showtimeId, isAuthenticated],
  );
  const { data, error, loading, reload, setData } = useApi(loader, [showtimeId, isAuthenticated], {
    interval: 20000,
  });
  useDocumentTitle(data?.movie?.title ? `Choose seats · ${data.movie.title}` : "Choose seats");

  useEffect(() => {
    if (isMobile) setView("2d");
  }, [isMobile]);

  const requestedSeats = useMemo(() => {
    const raw = searchParams.get("seats");
    if (!raw) return [];
    return raw
      .split(",")
      .map((seat) => seat.trim().toUpperCase())
      .filter(Boolean);
  }, [searchParams]);

  useEffect(() => {
    if (!data?.seats?.length) return;
    setSelected((current) => {
      const next = new Set();
      const byId = new Map(data.seats.map((seat) => [seat.seat_id, seat]));
      current.forEach((id) => {
        const seat = byId.get(id);
        if (seat?.status === "AVAILABLE") next.add(id);
      });
      if (!next.size && requestedSeats.length) {
        for (const id of requestedSeats) {
          const seat = byId.get(id);
          if (seat?.status === "AVAILABLE") next.add(id);
        }
      }
      if (next.size === current.size && [...next].every((id) => current.has(id))) return current;
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.seats]);

  const seats = data?.seats || [];
  const layout = data?.layout || {};
  const selectedSeats = useMemo(
    () => seats.filter((seat) => selected.has(seat.seat_id)),
    [seats, selected],
  );
  const total = selectedSeats.reduce((sum, seat) => sum + Number(seat.price || 0), 0);
  const availableCount = data?.summary?.available ?? 0;
  const currency = data?.currency || "MAD";

  const toggleSeat = useCallback(
    (seat) => {
      if (!seat || seat.status !== "AVAILABLE") {
        if (seat?.status === "HELD") {
          setNotice(
            seat.held_by_me
              ? "Those seats are already held for you. Resume your hold from the panel."
              : "Those seats are temporarily held by another guest.",
          );
        } else if (seat?.status === "BOOKED") {
          setNotice("That seat is already booked.");
        }
        return;
      }
      setNotice("");
      setHoldError(null);
      setSelected((current) => {
        const next = new Set(current);
        if (next.has(seat.seat_id)) {
          next.delete(seat.seat_id);
        } else {
          if (next.size >= MAX_SEATS) {
            setNotice(`You can choose up to ${MAX_SEATS} seats per booking.`);
            return current;
          }
          next.add(seat.seat_id);
        }
        return next;
      });
    },
    [],
  );

  const createHold = async () => {
    if (!selectedSeats.length || holding) return;
    if (!isAuthenticated) {
      navigate("/login", { state: { from: `/booking/${showtimeId}` } });
      return;
    }
    setHolding(true);
    setHoldError(null);
    try {
      const hold = await api("/holds", {
        method: "POST",
        body: { showtime_id: Number(showtimeId), seat_ids: selectedSeats.map((s) => s.seat_id) },
        timeout: 30000,
      });
      pushToast("Seats held — complete payment before the countdown ends.", "success");
      navigate(`/checkout/${hold.id}`);
    } catch (err) {
      const detail = err.detail;
      if (err.status === 409 && detail?.unavailable_seats) {
        const taken = new Set(detail.unavailable_seats);
        setSelected((current) => {
          const next = new Set(current);
          taken.forEach((id) => next.delete(id));
          return next;
        });
        setHoldError(
          `${detail.message || "Some seats were just taken."} Removed: ${[...taken].join(", ")}.`,
        );
        reload();
      } else {
        setHoldError(apiErrorMessage(err));
        if (err.status === 409 || err.status === 410) reload();
      }
    } finally {
      setHolding(false);
    }
  };

  if (loading) return <PageLoader label="Lighting the hall" />;
  if (error) {
    return (
      <div className="page page--narrow">
        <ErrorState
          error={error}
          title="We couldn't open this hall"
          onRetry={() => reload(true)}
        />
        <div className="center-actions">
          <Link to="/" className="btn btn--ghost btn--sm">
            <ArrowLeft size={14} /> Back to the programme
          </Link>
        </div>
      </div>
    );
  }
  if (!data) return null;

  const showtime = data.showtime || {};
  const movie = data.movie || {};
  const myHolds = data.my_holds || [];

  return (
    <div className="booking-page page">
      <div className="booking-topbar">
        <Link to={`/movies/${movie.id}`} className="back-link">
          <ArrowLeft size={15} /> {movie.title}
        </Link>
        <StepIndicator steps={STEPS} current={1} />
      </div>

      <header className="booking-head">
        <div className="booking-head-copy">
          <span className="eyebrow">Choose your seats</span>
          <h1>{movie.title}</h1>
          <div className="booking-when">
            <span>{formatDateLong(showtime.starts_at)}</span>
            <span className="dot" />
            <span>{showtime.time}</span>
            <span className="dot" />
            <span>{showtime.format_label}</span>
            <span className="dot" />
            <span>{showtime.language}</span>
          </div>
          <VenueLine data={data} />
        </div>
        <div className="booking-head-stat">
          <strong>{availableCount}</strong>
          <span>seats available</span>
          <small>Live from the reservation service</small>
        </div>
      </header>

      <ExistingHolds holds={myHolds} />

      {notice ? (
        <div className="inline-banner inline-banner--info" role="status">
          <TriangleAlert size={15} /> {notice}
        </div>
      ) : null}
      {holdError ? (
        <div className="inline-banner inline-banner--error" role="alert">
          <TriangleAlert size={15} /> {holdError}
        </div>
      ) : null}

      <div className="booking-layout">
        <section className="seat-stage" aria-label="Seat map">
          <div className="seat-stage-toolbar">
            <div className="seat-stage-title">
              <Armchair size={17} />
              <div>
                <strong>{data.hall?.name}</strong>
                <small>{data.hall?.screen_type} · {layout.seat_count || seats.length} seats</small>
              </div>
            </div>
            <div className="view-toggle" role="group" aria-label="Seat map view">
              <button
                type="button"
                className={view === "2d" ? "is-active" : ""}
                onClick={() => setView("2d")}
                aria-pressed={view === "2d"}
              >
                <LayoutGrid size={14} /> Plan
              </button>
              <button
                type="button"
                className={view === "3d" ? "is-active" : ""}
                onClick={() => {
                  if (!canUse3D) {
                    pushToast("This browser does not support the 3D hall. The seat plan still works.", "info");
                    return;
                  }
                  setView("3d");
                }}
                aria-pressed={view === "3d"}
                title={canUse3D ? "Interactive 3D hall" : "3D is not available in this browser"}
              >
                <Box size={14} /> 3D hall
              </button>
            </div>
          </div>

          {seats.length ? (
            view === "3d" ? (
              <SeatMap3D
                seats={seats}
                layout={layout}
                selectedIds={selected}
                onToggle={toggleSeat}
                onHover={setHovered}
              />
            ) : (
              <SeatPlan2D
                seats={seats}
                layout={layout}
                selectedIds={selected}
                onToggle={toggleSeat}
              />
            )
          ) : (
            <EmptyState
              title="No seat map for this screening"
              message="The hall layout has not been published yet."
            />
          )}

          <div className="seat-stage-foot">
            <Legend />
            <span className="seat-hover-readout">
              {hovered
                ? `${hovered.seat_id} · ${hovered.category} · ${money(hovered.price, currency)}`
                : "Hover a seat to inspect it"}
            </span>
          </div>
        </section>

        <aside className="order-panel" aria-label="Order summary">
          <div className="order-panel-head">
            <span className="eyebrow">Your selection</span>
            <h2>
              {selectedSeats.length
                ? `${selectedSeats.length} seat${selectedSeats.length === 1 ? "" : "s"}`
                : "Pick your seats"}
            </h2>
          </div>

          <div className="order-ticket">
            <div className="order-ticket-film">
              <div>
                <strong>{movie.title}</strong>
                <span>{showtime.format_label} · {showtime.language}</span>
              </div>
            </div>
            <dl>
              <div>
                <dt>Date</dt>
                <dd>{formatDateLong(showtime.starts_at)}</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>{showtime.time}</dd>
              </div>
              <div>
                <dt>House</dt>
                <dd>{data.cinema?.name}</dd>
              </div>
              <div>
                <dt>Hall</dt>
                <dd>{data.hall?.name}</dd>
              </div>
            </dl>
          </div>

          {selectedSeats.length ? (
            <div className="order-seats">
              <div className="order-seats-head">
                <span>Seats</span>
                <button type="button" className="text-btn" onClick={() => setSelected(new Set())}>
                  <RotateCcw size={12} /> Clear
                </button>
              </div>
              <ul>
                {selectedSeats
                  .slice()
                  .sort((a, b) => a.seat_id.localeCompare(b.seat_id))
                  .map((seat) => (
                    <li key={seat.seat_id}>
                      <span className="order-seat-id">{seat.seat_id}</span>
                      <span className="order-seat-meta">
                        {seat.category}
                        {seat.category !== "REGULAR" ? " · premium" : ""}
                      </span>
                      <strong>{money(seat.price, currency)}</strong>
                    </li>
                  ))}
              </ul>
            </div>
          ) : (
            <div className="order-empty">
              <Armchair size={22} />
              <p>Select up to {MAX_SEATS} seats on the plan. Your seats are only held once you confirm.</p>
            </div>
          )}

          <div className="order-totals">
            <div>
              <span>Subtotal</span>
              <span>{money(total, currency)}</span>
            </div>
            <div>
              <span>Booking fee</span>
              <span className="muted">Included</span>
            </div>
            <div className="order-total">
              <span>Total</span>
              <strong>{money(total, currency)}</strong>
            </div>
          </div>

          <button
            type="button"
            className="btn btn--gold btn--block btn--lg"
            disabled={!selectedSeats.length || holding}
            onClick={createHold}
          >
            {holding ? (
              <>
                <Spinner size={16} label="Holding seats" /> Holding seats…
              </>
            ) : (
              <>
                <Ticket size={16} /> Hold {selectedSeats.length || ""} seat{selectedSeats.length === 1 ? "" : "s"}
                <ArrowRight size={15} />
              </>
            )}
          </button>
          <p className="order-footnote">
            <ShieldCheck size={14} /> Seats are held for 5 minutes. You can release them any time
            before payment.
          </p>

          <button
            type="button"
            className="concierge-nudge"
            onClick={() =>
              window.dispatchEvent(
                new CustomEvent("nocturne:assistant-open", {
                  detail: { prompt: `Find me seats for ${movie.title}` },
                }),
              )
            }
          >
            <span className="concierge-nudge-icon">
              <Sparkles size={15} />
            </span>
            <span>
              <strong>Prefer to be guided?</strong>
              <small>Ask the concierge to choose seats for you</small>
            </span>
            <ArrowRight size={14} />
          </button>
        </aside>
      </div>

      <div className="booking-footnote">
        <span>
          <Clock3 size={14} /> Doors open 20 minutes before the screening.
        </span>
        <span>
          <Check size={14} /> Payment is simulated for this project.
        </span>
      </div>
    </div>
  );
}
