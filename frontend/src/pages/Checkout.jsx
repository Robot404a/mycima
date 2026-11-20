import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CreditCard,
  Landmark,
  LockKeyhole,
  MapPin,
  RotateCcw,
  ShieldCheck,
  Ticket,
  TriangleAlert,
  Wallet,
} from "lucide-react";
import { api, apiErrorMessage } from "../lib/api";
import { useApi, useDocumentTitle } from "../lib/hooks";
import { formatDateLong, formatTime, money, seatList } from "../lib/format";
import { fetchShowtime, normalizeHold } from "../lib/booking";
import { ErrorState, PageLoader, Poster, Spinner } from "../components/Feedback";
import { StepIndicator } from "../components/StepIndicator";
import { Countdown } from "../components/Countdown";
import { Modal } from "../components/Modal";
import { useAuth } from "../context/AuthContext";
import { useCurrency } from "../context/CurrencyContext";
import { useToast } from "../context/ToastContext";

const STEPS = ["Screening", "Seats", "Payment", "Ticket"];

function formatCardNumber(value) {
  return value
    .replace(/\D/g, "")
    .slice(0, 16)
    .replace(/(.{4})/g, "$1 ")
    .trim();
}

function formatExpiry(value) {
  const digits = value.replace(/\D/g, "").slice(0, 4);
  if (digits.length <= 2) return digits;
  return `${digits.slice(0, 2)}/${digits.slice(2)}`;
}

// A card expiry has to be a real month and a year that has not passed yet.
// Shape-only checks let values such as 77/77 through, so validate the date.
function expiryError(value) {
  const match = /^(\d{2})\/(\d{2})$/.exec(value);
  if (!match) return "Use MM/YY.";
  const month = Number(match[1]);
  if (month < 1 || month > 12) return "Month must be between 01 and 12.";
  const year = 2000 + Number(match[2]);
  const now = new Date();
  // The card stays valid through the last day of its expiry month.
  if (year < now.getFullYear() || (year === now.getFullYear() && month < now.getMonth() + 1)) {
    return "This card has expired.";
  }
  return "";
}

export default function Checkout() {
  const { holdId } = useParams();
  const navigate = useNavigate();
  const { pushToast } = useToast();
  const { user } = useAuth();
  const { currency } = useCurrency();
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState(null);
  const [releasing, setReleasing] = useState(false);
  const [releaseOpen, setReleaseOpen] = useState(false);
  const [expired, setExpired] = useState(false);
  const [form, setForm] = useState({ name: "", number: "", expiry: "", cvc: "" });
  const [touched, setTouched] = useState({});

  const loader = useCallback(async () => {
    const hold = await api(`/holds/${holdId}`);
    const showtime = await fetchShowtime(hold.showtime_id);
    return normalizeHold(hold, showtime);
  }, [holdId]);
  const { data: hold, error, loading, reload } = useApi(loader, [holdId]);
  useDocumentTitle("Payment");
  const snapshot = hold?.snapshot || {};
  const movie = snapshot.movie || {};
  const showtime = snapshot.showtime || {};
  const cinema = snapshot.cinema || {};
  const hall = snapshot.hall || {};

  useEffect(() => {
    if (hold?.status === "CONFIRMED" && hold?.booking_id) {
      setExpired(true);
    }
  }, [hold]);

  const cardValid = useMemo(() => {
    const digits = form.number.replace(/\D/g, "");
    return (
      form.name.trim().length >= 2 &&
      digits.length >= 15 &&
      !expiryError(form.expiry) &&
      /^\d{3,4}$/.test(form.cvc)
    );
  }, [form]);

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  // The booking belongs to the signed-in account, so the cardholder name is
  // detected from the profile instead of being typed again.
  useEffect(() => {
    if (!user?.full_name) return;
    setForm((current) => (current.name ? current : { ...current, name: user.full_name }));
  }, [user?.full_name]);

  const submit = async (event) => {
    event.preventDefault();
    if (!hold || paying) return;
    setTouched({ name: true, number: true, expiry: true, cvc: true });
    if (!cardValid) return;
    setPaying(true);
    setPayError(null);
    // The payment service charges the hold and confirms the booking with the reservation
    // service. The key makes a retried submit idempotent instead of charging twice.
    const idempotencyKey =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `pay-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    try {
      const payment = await api("/payments", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: { hold_id: holdId, method: "CARD", currency },
        timeout: 60000,
      });
      if (payment.status !== "SUCCEEDED") {
        setPayError(
          payment.failure_reason ||
            "The simulated payment was declined. Your seats stay held until the timer runs out.",
        );
        reload();
        return;
      }
      pushToast("Payment approved. Your ticket is ready.", "success");
      const bookings = await api("/bookings", { timeout: 30000 });
      const booking = (bookings?.bookings || []).find(
        (entry) => entry.hold_id === holdId || entry.hold_id === payment.hold_id,
      );
      if (booking) navigate(`/bookings/${booking.id}?new=1`, { replace: true });
      else navigate("/bookings", { replace: true });
    } catch (err) {
      if (err.status === 410) {
        setExpired(true);
        setPayError("Your hold has expired. The seats have been released.");
      } else if (err.status === 402) {
        setPayError(
          err.detail?.message ||
            "The simulated payment was declined. Your seats were released — choose seats again.",
        );
      } else {
        setPayError(apiErrorMessage(err));
      }
      reload();
    } finally {
      setPaying(false);
    }
  };

  const releaseHold = async () => {
    setReleasing(true);
    try {
      await api(`/holds/${holdId}`, { method: "DELETE" });
      pushToast("Seats released. No payment was taken.", "info");
      navigate(`/booking/${hold?.showtime_id}`);
    } catch (err) {
      pushToast(apiErrorMessage(err), "error");
      setReleasing(false);
      setReleaseOpen(false);
    }
  };

  if (loading) return <PageLoader label="Opening the cashier" />;
  if (error) {
    const gone = error.status === 404 || error.status === 410;
    return (
      <div className="page page--narrow checkout-error">
        <ErrorState
          error={error}
          title={gone ? "This hold is no longer available" : "We couldn't load your hold"}
          onRetry={gone ? undefined : () => reload(true)}
        />
        <div className="center-actions">
          <Link to="/" className="btn btn--ghost btn--sm">
            <ArrowLeft size={14} /> Back to the programme
          </Link>
        </div>
      </div>
    );
  }
  if (!hold) return null;

  const confirmed = hold.status === "CONFIRMED" && hold.booking_id;
  const inactive = expired || hold.status !== "ACTIVE" || hold.seconds_remaining <= 0;
  const expiryProblem = expiryError(form.expiry);

  return (
    <div className="checkout-page page">
      <div className="booking-topbar">
        <Link to={`/booking/${hold.showtime_id}`} className="back-link">
          <ArrowLeft size={15} /> Back to the seat map
        </Link>
        <StepIndicator steps={STEPS} current={2} />
      </div>

      <header className="checkout-head">
        <div>
          <span className="eyebrow">Almost there</span>
          <h1>Complete your booking</h1>
          <p>Your seats are held. Review the order and approve the simulated payment.</p>
        </div>
        <div className={`checkout-clock ${inactive ? "is-expired" : ""}`}>
          <span>Time left</span>
          <Countdown
            expiresAt={hold.expires_at}
            onExpire={() => {
              setExpired(true);
              reload();
            }}
            compact
            label=""
          />
        </div>
      </header>

      {confirmed ? (
        <div className="inline-banner inline-banner--success">
          <Check size={16} /> This hold is already confirmed.{" "}
          <Link to={`/bookings/${hold.booking_id}`}>View your ticket</Link>
        </div>
      ) : null}
      {inactive && !confirmed ? (
        <div className="inline-banner inline-banner--error" role="alert">
          <TriangleAlert size={16} /> This hold has expired and the seats were released. Choose seats
          again to continue.
        </div>
      ) : null}
      {payError ? (
        <div className="inline-banner inline-banner--error" role="alert">
          <TriangleAlert size={16} /> {payError}
        </div>
      ) : null}

      <div className="checkout-layout">
        <section className="checkout-main">
          {!confirmed && !inactive ? (
            <form className="payment-card" onSubmit={submit}>
              <div className="payment-card-head">
                <div>
                  <span className="eyebrow">Simulated payment</span>
                  <h2>Card details</h2>
                </div>
                <span className="payment-secure">
                  <LockKeyhole size={14} /> Demo only
                </span>
              </div>

              <div className="payment-methods" role="group" aria-label="Payment method">
                <button type="button" className="payment-method is-active" aria-pressed="true">
                  <CreditCard size={17} />
                  <span>
                    <strong>Card</strong>
                    <small>Visa · Mastercard</small>
                  </span>
                </button>
                <button
                  type="button"
                  className="payment-method"
                  aria-pressed="false"
                  onClick={() => pushToast("Cash and wallet payments are not enabled in this simulation.", "info")}
                >
                  <Wallet size={17} />
                  <span>
                    <strong>Wallet</strong>
                    <small>Coming later</small>
                  </span>
                </button>
                <button
                  type="button"
                  className="payment-method"
                  aria-pressed="false"
                  onClick={() => pushToast("Bank transfers are not enabled in this simulation.", "info")}
                >
                  <Landmark size={17} />
                  <span>
                    <strong>Bank</strong>
                    <small>Coming later</small>
                  </span>
                </button>
              </div>

              <div className="field-grid">
                <label className="field field--full">
                  <span>Name on card</span>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(event) => update("name", event.target.value)}
                    onBlur={() => setTouched((current) => ({ ...current, name: true }))}
                    placeholder="As printed on the card"
                    autoComplete="cc-name"
                    aria-invalid={touched.name && form.name.trim().length < 2}
                  />
                  {touched.name && form.name.trim().length < 2 ? (
                    <small className="field-error">Enter the cardholder name.</small>
                  ) : null}
                </label>
                <label className="field field--full">
                  <span>Card number</span>
                  <div className="input-with-icon">
                    <CreditCard size={16} />
                    <input
                      type="text"
                      inputMode="numeric"
                      value={form.number}
                      onChange={(event) => update("number", formatCardNumber(event.target.value))}
                      onBlur={() => setTouched((current) => ({ ...current, number: true }))}
                      placeholder="4242 4242 4242 4242"
                      autoComplete="cc-number"
                      aria-invalid={touched.number && form.number.replace(/\D/g, "").length < 15}
                    />
                  </div>
                  {touched.number && form.number.replace(/\D/g, "").length < 15 ? (
                    <small className="field-error">Enter a 16-digit card number.</small>
                  ) : null}
                </label>
                <label className="field">
                  <span>Expiry</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={form.expiry}
                    onChange={(event) => update("expiry", formatExpiry(event.target.value))}
                    onBlur={() => setTouched((current) => ({ ...current, expiry: true }))}
                    placeholder="MM/YY"
                    autoComplete="cc-exp"
                    aria-invalid={touched.expiry && Boolean(expiryProblem)}
                  />
                  {touched.expiry && expiryProblem ? (
                    <small className="field-error">{expiryProblem}</small>
                  ) : null}
                </label>
                <label className="field">
                  <span>CVC</span>
                  <input
                    type="password"
                    inputMode="numeric"
                    value={form.cvc}
                    onChange={(event) => update("cvc", event.target.value.replace(/\D/g, "").slice(0, 4))}
                    onBlur={() => setTouched((current) => ({ ...current, cvc: true }))}
                    placeholder="123"
                    autoComplete="cc-csc"
                    aria-invalid={touched.cvc && !/^\d{3,4}$/.test(form.cvc)}
                  />
                  {touched.cvc && !/^\d{3,4}$/.test(form.cvc) ? (
                    <small className="field-error">3 or 4 digits.</small>
                  ) : null}
                </label>
              </div>

              <div className="payment-demo-row">
                <button
                  type="button"
                  className="text-btn"
                  onClick={() =>
                    setForm({
                      name: "MyCima Guest",
                      number: "4242 4242 4242 4242",
                      expiry: "12/29",
                      cvc: "123",
                    })
                  }
                >
                  Use demo card details
                </button>
                <span>No real charge is made. Nothing is stored.</span>
              </div>

              <button
                type="submit"
                className="btn btn--gold btn--block btn--lg"
                disabled={paying || inactive || !cardValid}
              >
                {paying ? (
                  <>
                    <Spinner size={16} label="Processing payment" /> Processing payment…
                  </>
                ) : (
                  <>
                    <LockKeyhole size={15} /> Pay {money(hold.total_price, hold.currency)}
                  </>
                )}
              </button>
              <p className="payment-disclaimer">
                <ShieldCheck size={14} /> This is a university project simulation. Payment runs
                through the reservation and payment services, but no money moves.
              </p>
            </form>
          ) : confirmed ? (
            <div className="state-card state-card--success checkout-confirmed">
              <span className="state-icon">
                <Check size={24} />
              </span>
              <h3>Payment already approved</h3>
              <p>Your seats are confirmed and the ticket is in your bookings.</p>
              <Link to={`/bookings/${hold.booking_id}`} className="btn btn--gold btn--sm">
                Open your ticket <ArrowRight size={14} />
              </Link>
            </div>
          ) : (
            <div className="state-card state-card--error checkout-expired">
              <span className="state-icon">
                <TriangleAlert size={24} />
              </span>
              <h3>The hold has expired</h3>
              <p>Seats are released back to the room after five minutes. Pick your seats again.</p>
              <Link to={`/booking/${hold.showtime_id}`} className="btn btn--gold btn--sm">
                <RotateCcw size={14} /> Choose seats again
              </Link>
            </div>
          )}

          <div className="checkout-assurance">
            <div>
              <Ticket size={17} />
              <strong>Instant ticket</strong>
              <span>A reference and in-app notification the moment payment succeeds.</span>
            </div>
            <div>
              <RotateCcw size={17} />
              <strong>Cancel up to 2 hours before</strong>
              <span>Simulated refunds return to your original card.</span>
            </div>
          </div>
        </section>

        <aside className="checkout-summary" aria-label="Order summary">
          <div className="checkout-summary-head">
            <span className="eyebrow">Order summary</span>
            <Link to={`/movies/${movie.id}`} className="text-btn">
              Change seats
            </Link>
          </div>
          <div className="checkout-film">
            <Poster src={movie.poster_url} title={movie.title} />
            <div>
              <h3>{movie.title}</h3>
              <p>{showtime.format_label || showtime.format} · {showtime.language}</p>
              <span className="age-chip">{movie.age_rating}</span>
            </div>
          </div>
          <div className="checkout-contact">
            <span>Contact</span>
            <strong>{user?.email || "—"}</strong>
            <small>Detected from your account — your ticket and receipt go here.</small>
          </div>
          <dl className="checkout-details">
            <div>
              <dt>Date</dt>
              <dd>{formatDateLong(showtime.starts_at)}</dd>
            </div>
            <div>
              <dt>Time</dt>
              <dd>{showtime.time || formatTime(showtime.starts_at)}</dd>
            </div>
            <div>
              <dt>Cinema</dt>
              <dd>
                <MapPin size={13} /> {cinema.name}
              </dd>
            </div>
            <div>
              <dt>Hall</dt>
              <dd>{hall.name}</dd>
            </div>
          </dl>
          <div className="checkout-seats">
            <span>Seats</span>
            <strong>{seatList(hold.seats) || "—"}</strong>
            <div className="checkout-seat-chips">
              {(hold.seats || []).map((seat) => {
                const label = typeof seat === "string" ? seat : seat.seat_id;
                const category =
                  (typeof seat === "string" ? "regular" : seat.category || "regular").toLowerCase();
                const price =
                  typeof seat === "string"
                    ? Number(hold.total_price || 0) / (hold.seats.length || 1)
                    : seat.price;
                return (
                  <span key={label} className={`seat-chip seat-chip--${category}`}>
                    {label}
                    <small>{money(price, hold.currency)}</small>
                  </span>
                );
              })}
            </div>
          </div>
          <div className="checkout-totals">
            <div>
              <span>Subtotal</span>
              <span>{money(hold.total_price, hold.currency)}</span>
            </div>
            <div>
              <span>Booking fee</span>
              <span className="muted">Included</span>
            </div>
            <div>
              <span>Taxes</span>
              <span className="muted">Included</span>
            </div>
            <div className="checkout-total">
              <span>Total due</span>
              <strong>{money(hold.total_price, hold.currency)}</strong>
            </div>
          </div>
          {!confirmed ? (
            <button
              type="button"
              className="text-btn text-btn--danger release-btn"
              onClick={() => setReleaseOpen(true)}
            >
              Release these seats
            </button>
          ) : null}
        </aside>
      </div>

      <Modal
        open={releaseOpen}
        onClose={() => setReleaseOpen(false)}
        title="Release your seats?"
        subtitle="The seats return to the room immediately and no payment is taken."
        size="sm"
        footer={
          <>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setReleaseOpen(false)}>
              Keep my seats
            </button>
            <button
              type="button"
              className="btn btn--danger btn--sm"
              onClick={releaseHold}
              disabled={releasing}
            >
              {releasing ? <Spinner size={14} label="Releasing" /> : null} Release seats
            </button>
          </>
        }
      >
        <p className="modal-copy">
          You can choose different seats afterwards, but the ones you are holding now may be taken
          by another guest in the meantime.
        </p>
      </Modal>
    </div>
  );
}
