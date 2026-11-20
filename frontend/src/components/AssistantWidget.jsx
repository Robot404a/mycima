import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CalendarDays,
  Check,
  MessageCircle,
  Plus,
  Send,
  Sparkles,
  Ticket,
  X,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { api, apiErrorMessage, getToken } from "../lib/api";
import { useCountdown, useLockBody, useMediaQuery } from "../lib/hooks";
import { formatCountdown, formatDateShort, money, seatList } from "../lib/format";
import { Poster } from "./Feedback";
import { RichText } from "./RichText";

const SESSION_KEY = "nocturne.assistant.session";

const SUGGESTIONS = [
  "Two seats together for a comedy tomorrow evening",
  "What should I watch if I want something mind-bending?",
  "Find me IMAX seats for Dune this week",
];

function HoldCard({ hold, onCheckout }) {
  const { seconds, expired } = useCountdown(hold?.expires_at);
  if (!hold) return null;
  return (
    <div className={`assistant-hold ${expired ? "is-expired" : ""}`}>
      <div className="assistant-hold-top">
        <span className="assistant-card-kicker">
          <Ticket size={13} /> Seats held
        </span>
        {!expired ? <span className="assistant-timer">{formatCountdown(seconds)}</span> : <span className="assistant-timer">Expired</span>}
      </div>
      <strong>{hold.movie?.title}</strong>
      <p>
        {formatDateShort(hold.starts_at)} · {hold.time} · {hold.cinema}
      </p>
      <p className="assistant-seats">Seats {seatList(hold.seats)}</p>
      <div className="assistant-hold-bottom">
        <span>{money(hold.total_price, hold.currency)}</span>
        <button type="button" className="btn btn--gold btn--xs" onClick={() => onCheckout(hold.id)}>
          Confirm and pay <ArrowRight size={13} />
        </button>
      </div>
    </div>
  );
}

function PendingCard({ pending, onConfirm, onView, loading }) {
  if (!pending) return null;
  return (
    <div className="assistant-pending">
      <div className="assistant-pending-film">
        <Poster src={pending.movie?.poster_url} title={pending.movie?.title} />
        <div>
          <span className="assistant-card-kicker">
            <Sparkles size={13} /> Suggested for you
          </span>
          <strong>{pending.movie?.title}</strong>
          <p>
            {formatDateShort(pending.starts_at)} · {pending.time}
            {pending.format ? ` · ${pending.format}` : ""}
          </p>
          <p>
            {pending.cinema}
            {pending.hall ? ` · ${pending.hall}` : ""}
          </p>
        </div>
      </div>
      <div className="assistant-pending-seats">
        <span>Seats {pending.seat_ids?.join(", ")}</span>
        <strong>{money(pending.total_price, pending.currency)}</strong>
      </div>
      <div className="assistant-pending-actions">
        <button type="button" className="btn btn--gold btn--xs" onClick={onConfirm} disabled={loading}>
          {loading ? "Holding…" : "Hold these seats"}
        </button>
        <button type="button" className="btn btn--ghost btn--xs" onClick={onView}>
          View seat map
        </button>
      </div>
      <small className="assistant-disclaimer">Seats are only held after you confirm.</small>
    </div>
  );
}

export function AssistantWidget() {
  const { isAuthenticated, ready, user } = useAuth();
  const { pushToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const isMobile = useMediaQuery("(max-width: 760px)");
  const [open, setOpen] = useState(false);
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) || null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [pending, setPending] = useState(null);
  const [hold, setHold] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  useLockBody(open && isMobile);

  useEffect(() => {
    const handler = (event) => {
      setOpen(true);
      if (event.detail?.prompt) {
        setInput(event.detail.prompt);
      }
    };
    window.addEventListener("nocturne:assistant-open", handler);
    return () => window.removeEventListener("nocturne:assistant-open", handler);
  }, []);

  useEffect(() => {
    if (!open) return;
    setTimeout(() => inputRef.current?.focus(), 120);
  }, [open]);

  useEffect(() => {
    if (!open || !isAuthenticated || !sessionId || messages.length) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await api(`/assistant/sessions/${sessionId}`);
        if (cancelled) return;
        setMessages(
          (data.messages || []).map((item) => ({
            id: item.id,
            role: item.role,
            text: item.content,
          })),
        );
        if (data.pending_confirmation) setPending(data.pending_confirmation);
        if (data.last_hold) setHold(data.last_hold);
      } catch {
        if (!cancelled) {
          localStorage.removeItem(SESSION_KEY);
          setSessionId(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, isAuthenticated, sessionId, messages.length]);

  useEffect(() => {
    if (!open) return;
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [open, messages, pending, hold, sending]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const newConversation = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setPending(null);
    setHold(null);
    setError("");
    setInput("");
    localStorage.removeItem(SESSION_KEY);
    setTimeout(() => inputRef.current?.focus(), 100);
  }, []);

  const send = useCallback(
    async (rawText) => {
      const text = (rawText ?? input).trim();
      if (!text || sending) return;
      if (!isAuthenticated) {
        pushToast("Sign in to speak with the concierge.", "info");
        return;
      }
      setInput("");
      setError("");
      setMessages((current) => [
        ...current,
        { id: `local-${Date.now()}`, role: "user", text },
      ]);
      setSending(true);
      try {
        const data = await api("/assistant/chat", {
          method: "POST",
          body: { message: text, session_id: sessionId || undefined },
          timeout: 110000,
        });
        setSessionId(data.session_id);
        localStorage.setItem(SESSION_KEY, data.session_id);
        setMessages((current) => [
          ...current,
          { id: `reply-${Date.now()}`, role: "assistant", text: data.reply },
        ]);
        setPending(data.pending_confirmation || null);
        if (data.hold) {
          setHold(data.hold);
          window.dispatchEvent(new CustomEvent("nocturne:hold-created", { detail: data.hold }));
        }
      } catch (err) {
        const message = apiErrorMessage(err);
        setError(message);
        setMessages((current) => [
          ...current,
          {
            id: `error-${Date.now()}`,
            role: "assistant",
            text: "I couldn't reach the booking engine just now. Manual booking still works — open a film and choose your seats on the map.",
            error: true,
          },
        ]);
      } finally {
        setSending(false);
      }
    },
    [input, sending, isAuthenticated, pushToast, sessionId],
  );

  const confirmHold = async () => {
    if (!pending || confirming) return;
    setConfirming(true);
    setError("");
    try {
      const data = await api("/assistant/confirm-hold", {
        method: "POST",
        body: { session_id: sessionId },
        timeout: 60000,
      });
      setHold(data.hold);
      setPending(null);
      setMessages((current) => [
        ...current,
        { id: `held-${Date.now()}`, role: "assistant", text: data.message },
      ]);
      pushToast("Seats held. Complete payment before the countdown ends.", "success");
      window.dispatchEvent(new CustomEvent("nocturne:hold-created", { detail: data.hold }));
    } catch (err) {
      setError(apiErrorMessage(err));
      if ([409, 410].includes(err.status)) setPending(null);
    } finally {
      setConfirming(false);
    }
  };

  const openSeatMap = () => {
    if (!pending) return;
    navigate(
      `/booking/${pending.showtime_id}?seats=${encodeURIComponent((pending.seat_ids || []).join(","))}`,
    );
    setOpen(false);
  };

  const goCheckout = (holdId) => {
    navigate(`/checkout/${holdId}`);
    setOpen(false);
  };

  const showSuggestions = !messages.length && !pending && !hold;

  return (
    <>
      {!open ? (
        <button
          type="button"
          className="assistant-fab"
          onClick={() => setOpen(true)}
          aria-label="Open the Nocturne concierge"
        >
          <span className="assistant-fab-glow" />
          <MessageCircle size={20} />
        </button>
      ) : null}

      {open ? (
        <>
          {isMobile ? <div className="assistant-backdrop" onClick={() => setOpen(false)} /> : null}
          <aside className={`assistant-panel ${open ? "is-open" : ""}`} aria-label="Nocturne concierge">
            <header className="assistant-head">
              <div className="assistant-identity">
                <span className="assistant-orb">
                  <Sparkles size={17} />
                </span>
                <div>
                  <strong>The concierge</strong>
                  <small>Seats, films & late-night advice</small>
                </div>
              </div>
              <div className="assistant-head-actions">
                <button type="button" className="icon-btn" onClick={newConversation} title="New conversation">
                  <Plus size={17} />
                </button>
                <button type="button" className="icon-btn" onClick={() => setOpen(false)} aria-label="Close concierge">
                  <X size={18} />
                </button>
              </div>
            </header>

            {!isAuthenticated ? (
              <div className="assistant-signin">
                <span className="assistant-orb assistant-orb--lg">
                  <Sparkles size={24} />
                </span>
                <h3>A quieter way to choose</h3>
                <p>
                  Sign in and tell me the mood, the film or the number of seats. I'll find a
                  screening and propose seats — you stay in control of the final payment.
                </p>
                <button
                  type="button"
                  className="btn btn--gold btn--sm"
                  onClick={() => {
                    navigate("/login", { state: { from: location.pathname } });
                    setOpen(false);
                  }}
                >
                  Sign in to chat
                </button>
              </div>
            ) : (
              <>
                <div className="assistant-scroll" ref={scrollRef}>
                  {showSuggestions ? (
                    <div className="assistant-welcome">
                      <span className="eyebrow">Good evening{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}</span>
                      <h3>What are we seeing?</h3>
                      <p>
                        I can search the programme, compare screens and propose the best available
                        seats. I never take payment — that last step stays with you.
                      </p>
                      <div className="assistant-suggestions">
                        {SUGGESTIONS.map((suggestion) => (
                          <button key={suggestion} type="button" onClick={() => send(suggestion)}>
                            {suggestion}
                            <ArrowRight size={14} />
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`chat-message chat-message--${message.role} ${message.error ? "is-error" : ""}`}
                    >
                      {message.role === "assistant" ? (
                        <span className="chat-avatar">
                          <Sparkles size={13} />
                        </span>
                      ) : null}
                      <div className="chat-bubble">
                        <RichText text={message.text} />
                      </div>
                    </div>
                  ))}

                  {sending ? (
                    <div className="chat-message chat-message--assistant">
                      <span className="chat-avatar">
                        <Sparkles size={13} />
                      </span>
                      <div className="chat-bubble typing">
                        <span />
                        <span />
                        <span />
                      </div>
                    </div>
                  ) : null}

                  <PendingCard
                    pending={pending}
                    loading={confirming}
                    onConfirm={confirmHold}
                    onView={openSeatMap}
                  />
                  <HoldCard hold={hold} onCheckout={goCheckout} />
                  {error ? <div className="assistant-inline-error">{error}</div> : null}
                </div>

                <footer className="assistant-composer">
                  <div className="assistant-input-wrap">
                    <textarea
                      ref={inputRef}
                      value={input}
                      onChange={(event) => setInput(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && !event.shiftKey) {
                          event.preventDefault();
                          send();
                        }
                      }}
                      rows={1}
                      placeholder="Two seats for a comedy tomorrow…"
                      aria-label="Message the concierge"
                    />
                    <button
                      type="button"
                      className="assistant-send"
                      onClick={() => send()}
                      disabled={sending || !input.trim()}
                      aria-label="Send message"
                    >
                      <Send size={16} />
                    </button>
                  </div>
                  <small>
                    <Check size={12} /> Seat availability is verified live. Payment is always your step.
                  </small>
                </footer>
              </>
            )}
          </aside>
        </>
      ) : null}
    </>
  );
}
