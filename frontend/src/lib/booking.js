/**
 * Adapters between the reservation service and the shape the cinema UI renders.
 *
 * The reservation service stores money and seats in its own compact form and
 * returns lowercase statuses; the movie service owns the film, hall and cinema
 * details. These helpers join both into one view model.
 */
import { api } from "./api";
import { formatTime } from "./format";

const STATUS_MAP = {
  booked: "BOOKED",
  held: "HELD",
  available: "AVAILABLE",
};

export async function fetchShowtime(showtimeId) {
  if (!showtimeId) return null;
  try {
    return await api(`/showtimes/${showtimeId}`, { auth: false });
  } catch {
    return null;
  }
}

export function ticketReference(booking) {
  if (booking.reference) return booking.reference;
  const id = String(booking.id || "");
  return id ? id.slice(0, 8).toUpperCase() : "MYCIMA";
}

export function snapshotFromShowtime(showtime) {
  if (!showtime) return {};
  const movie = showtime.movie || {};
  return {
    movie: {
      ...movie,
      duration_min: movie.duration_min || movie.duration_minutes,
      age_rating: movie.age_rating || "TBC",
      tagline: movie.tagline || "",
    },
    showtime: {
      ...showtime,
      time: showtime.time || formatTime(showtime.starts_at),
      format_label: showtime.format_label || showtime.format,
      language: showtime.language || movie.language,
    },
    cinema: showtime.cinema || {},
    hall: showtime.hall || {},
  };
}

export function normalizeHold(hold, showtime) {
  if (!hold) return null;
  return {
    ...hold,
    // The reservation service uses lowercase statuses and calls a paid hold "converted".
    status: hold.status === "converted" ? "CONFIRMED" : String(hold.status || "").toUpperCase(),
    total_price: hold.total_price ?? hold.total ?? 0,
    currency: hold.currency || showtime?.currency || "MAD",
    seconds_remaining: hold.seconds_remaining ?? hold.seconds_left ?? 0,
    snapshot: hold.snapshot || snapshotFromShowtime(showtime),
  };
}

export function normalizeBooking(booking, showtime) {
  if (!booking) return null;
  const status = String(booking.status || "").toUpperCase();
  return {
    ...booking,
    status,
    reference: ticketReference(booking),
    total_price: booking.total_price ?? booking.total_amount ?? 0,
    currency: booking.currency || showtime?.currency || "MAD",
    starts_at: booking.starts_at || showtime?.starts_at,
    payment_transaction_id: booking.payment_transaction_id || booking.payment_ref,
    refund_status: booking.refund_status ?? (status === "CANCELLED" ? "Refunded" : null),
    can_cancel: booking.can_cancel ?? status === "CONFIRMED",
    snapshot: booking.snapshot || snapshotFromShowtime(showtime),
  };
}

/** Loads the showtime of every booking once and returns enriched bookings. */
export async function hydrateBookings(bookings = []) {
  const showtimes = new Map();
  const ids = [...new Set(bookings.map((booking) => booking.showtime_id).filter(Boolean))];
  await Promise.all(
    ids.map(async (id) => {
      showtimes.set(id, await fetchShowtime(id));
    }),
  );
  return bookings.map((booking) => normalizeBooking(booking, showtimes.get(booking.showtime_id)));
}

/**
 * Enrich admin bookings and holds (lowercase statuses, no snapshot) with the
 * movie/hall/cinema they belong to. One showtime lookup per screening.
 */
export async function hydrateAdminActivity(bookings = [], holds = []) {
  const ids = [
    ...new Set([...bookings, ...holds].map((entry) => entry.showtime_id).filter(Boolean)),
  ];
  const showtimes = new Map();
  await Promise.all(
    ids.map(async (id) => {
      showtimes.set(id, await fetchShowtime(id));
    }),
  );
  return {
    bookings: bookings.map((booking) => normalizeBooking(booking, showtimes.get(booking.showtime_id))),
    holds: holds.map((hold) => normalizeHold(hold, showtimes.get(hold.showtime_id))),
  };
}

/** Builds the seat-map view model from the reservation seats + movie showtime. */
export function seatMapFrom(seatData, showtime, holds = []) {
  const rows = seatData?.rows || [];
  const rowIndex = new Map(rows.map((row, index) => [row, index]));
  const price = showtime?.price ?? seatData?.price ?? 0;
  const seats = (seatData?.seats || []).map((seat) => ({
    seat_id: seat.label,
    row_label: seat.row,
    seat_number: seat.number,
    x: seat.number,
    y: rowIndex.get(seat.row) ?? 0,
    status: STATUS_MAP[seat.status] || "AVAILABLE",
    held_by_me: Boolean(seat.mine),
    category: seat.category ? String(seat.category).toUpperCase() : "REGULAR",
    // VIP rows are priced by the reservation service, so trust the seat price.
    price: seat.price ?? price,
  }));

  return {
    showtime: showtime
      ? {
          ...showtime,
          time: formatTime(showtime.starts_at),
          format_label: showtime.format,
        }
      : {},
    movie: showtime?.movie || {},
    cinema: showtime?.cinema || {},
    hall: showtime?.hall || {},
    layout: {
      row_count: rows.length || showtime?.hall?.rows,
      max_x: seatData?.seats_per_row || showtime?.hall?.seats_per_row,
      aisles_after: showtime?.hall?.aisle_after || [],
      seat_count: seats.length,
    },
    seats,
    summary: {
      available: seats.filter((seat) => seat.status === "AVAILABLE").length,
      total: seats.length,
    },
    currency: showtime?.currency || "MAD",
    my_holds: (holds || [])
      .filter((hold) => Number(hold.showtime_id) === Number(seatData?.showtime_id ?? showtime?.id))
      .map((hold) => ({ ...hold, total_price: hold.total_price ?? hold.total ?? 0 })),
  };
}
