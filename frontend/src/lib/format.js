export const CINEMA_TIMEZONE = "Africa/Casablanca";

const dateLong = new Intl.DateTimeFormat("en-GB", {
  timeZone: CINEMA_TIMEZONE,
  weekday: "long",
  day: "numeric",
  month: "long",
});

const dateShort = new Intl.DateTimeFormat("en-GB", {
  timeZone: CINEMA_TIMEZONE,
  weekday: "short",
  day: "numeric",
  month: "short",
});

const monthShort = new Intl.DateTimeFormat("en-GB", {
  timeZone: CINEMA_TIMEZONE,
  month: "short",
});

const dayNumber = new Intl.DateTimeFormat("en-GB", {
  timeZone: CINEMA_TIMEZONE,
  day: "numeric",
});

const weekdayShort = new Intl.DateTimeFormat("en-GB", {
  timeZone: CINEMA_TIMEZONE,
  weekday: "short",
});

const timeFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: CINEMA_TIMEZONE,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const fullFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: CINEMA_TIMEZONE,
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function toDate(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateLong(value) {
  const date = toDate(value);
  return date ? dateLong.format(date) : "—";
}

export function formatDateShort(value) {
  const date = toDate(value);
  return date ? dateShort.format(date) : "—";
}

export function formatTime(value) {
  const date = toDate(value);
  return date ? timeFormat.format(date) : "—";
}

export function formatDateTime(value) {
  const date = toDate(value);
  return date ? fullFormat.format(date) : "";
}

export function cinemaToday() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: CINEMA_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

/** Calendar day (YYYY-MM-DD in cinema time) of an ISO timestamp. */
export function cinemaDay(value) {
  const date = toDate(value);
  if (!date) return "";
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: CINEMA_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export function dateFromDayString(day) {
  return new Date(`${day}T12:00:00+01:00`);
}

export function dayParts(day) {
  const date = dateFromDayString(day);
  return {
    weekday: weekdayShort.format(date),
    day: dayNumber.format(date),
    month: monthShort.format(date),
  };
}

export function relativeDayLabel(day) {
  const today = cinemaToday();
  if (day === today) return "Today";
  const tomorrow = new Date(`${today}T12:00:00Z`);
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  const tomorrowString = tomorrow.toISOString().slice(0, 10);
  if (day === tomorrowString) return "Tomorrow";
  return dateShort.format(dateFromDayString(day));
}

export const CURRENCY_LABELS = { MAD: "DH", EUR: "€" };
export const MAD_TO_EUR = 0.092;

let displayCurrency = "MAD";

export function setDisplayCurrency(code) {
  displayCurrency = code === "EUR" ? "EUR" : "MAD";
}

export function getDisplayCurrency() {
  return displayCurrency;
}

export function convertAmount(amount, from = "MAD", to = displayCurrency) {
  const source = String(from || "MAD").toUpperCase();
  if (source === to) return amount;
  if (source === "MAD" && to === "EUR") return amount * MAD_TO_EUR;
  if (source === "EUR" && to === "MAD") return amount / MAD_TO_EUR;
  return amount;
}

export function money(value, currency = "MAD") {
  const amount = Number(value);
  const label = CURRENCY_LABELS[displayCurrency] || displayCurrency;
  if (!Number.isFinite(amount)) return `— ${label}`;
  const converted = convertAmount(amount, currency, displayCurrency);
  return `${converted.toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${label}`;
}

export function duration(minutes) {
  if (!minutes) return "";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest} min`;
  return `${hours}h ${rest.toString().padStart(2, "0")}`;
}

export function initials(name = "") {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

export function formatCountdown(seconds) {
  const safe = Math.max(0, Math.floor(seconds));
  const mins = Math.floor(safe / 60);
  const secs = safe % 60;
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

export function relativeTime(value) {
  if (!value) return "";
  const then = new Date(value).getTime();
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 60) return "Just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} d ago`;
  return formatDateShort(value);
}

export function classNames(...items) {
  return items.filter(Boolean).join(" ");
}

export function seatLabel(seat) {
  if (!seat) return "";
  // The reservation service returns seat labels; other endpoints return seat objects.
  if (typeof seat === "string") return seat;
  return seat.seat_id || `${seat.row_label ?? ""}${seat.seat_number ?? ""}`;
}

export function seatList(seats = []) {
  return seats.map(seatLabel).join(", ");
}

export function pluralize(count, singular, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

export function isoDateForInput(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}
