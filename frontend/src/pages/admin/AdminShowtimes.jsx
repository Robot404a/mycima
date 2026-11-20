import { useCallback, useMemo, useState } from "react";
import {
  CalendarPlus,
  CalendarRange,
  Clapperboard,
  Pencil,
  Power,
  Search,
} from "lucide-react";
import { api, apiErrorMessage } from "../../lib/api";
import { useApi, useDocumentTitle } from "../../lib/hooks";
import { formatDateLong, money } from "../../lib/format";
import { ErrorState, PageLoader, Spinner } from "../../components/Feedback";
import { Modal } from "../../components/Modal";
import { useToast } from "../../context/ToastContext";
import {
  AdminEmpty,
  AdminPageHead,
  AdminSearch,
  ConfirmDialog,
  FieldError,
  StatusPill,
} from "./ui";

const FORMATS = [
  ["STANDARD", "2D · Standard"],
  ["THREE_D", "3D"],
  ["IMAX", "IMAX"],
];

function cinemaInputValue(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Africa/Casablanca",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const map = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${map.year}-${map.month}-${map.day}T${map.hour}:${map.minute}`;
}

function defaultStart() {
  const date = new Date(Date.now() + 24 * 60 * 60 * 1000);
  date.setMinutes(0, 0, 0);
  date.setHours(20);
  return cinemaInputValue(date.toISOString());
}

function emptyForm(movies, halls) {
  const firstMovie = movies[0];
  const firstHall = halls[0];
  return {
    movie_id: firstMovie ? String(firstMovie.id) : "",
    hall_id: firstHall ? String(firstHall.id) : "",
    starts_at: defaultStart(),
    format: firstHall?.supported_formats?.[0] || "STANDARD",
    language: "English",
    base_price: "80",
    is_active: true,
  };
}

function formatOption(value) {
  const key = String(value || "").toUpperCase();
  if (key === "3D" || key === "THREE_D") return "THREE_D";
  if (key === "IMAX") return "IMAX";
  return "STANDARD";
}

function toForm(showtime) {
  return {
    movie_id: String(showtime.movie_id),
    hall_id: String(showtime.hall?.id),
    starts_at: cinemaInputValue(showtime.starts_at),
    format: formatOption(showtime.format_value || showtime.format),
    language: showtime.language || "English",
    base_price: String(showtime.base_price),
    is_active: showtime.is_active,
  };
}

function ShowtimeForm({ open, onClose, showtime, movies, halls, onSaved }) {
  const { pushToast } = useToast();
  const [form, setForm] = useState(() =>
    showtime ? toForm(showtime) : emptyForm(movies, halls),
  );
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const selectedHall = halls.find((hall) => String(hall.id) === String(form.hall_id));
  const formats = selectedHall?.supported_formats?.length
    ? FORMATS.filter(([value]) => selectedHall.supported_formats.includes(value))
    : FORMATS;

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const onHallChange = (value) => {
    const hall = halls.find((entry) => String(entry.id) === String(value));
    setForm((current) => {
      const allowed = hall?.supported_formats?.length ? hall.supported_formats : ["STANDARD"];
      return {
        ...current,
        hall_id: value,
        format: allowed.includes(current.format) ? current.format : allowed[0],
      };
    });
  };

  const submit = async (event) => {
    event.preventDefault();
    if (saving) return;
    const errors = {};
    if (!form.movie_id) errors.movie_id = "Choose a film.";
    if (!form.hall_id) errors.hall_id = "Choose a hall.";
    if (!form.starts_at) errors.starts_at = "Choose a date and time.";
    const price = Number(form.base_price);
    if (!Number.isFinite(price) || price <= 0) errors.base_price = "Enter a price above zero.";
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;
    setError("");
    setSaving(true);
    const payload = {
      movie_id: Number(form.movie_id),
      hall_id: Number(form.hall_id),
      starts_at: form.starts_at,
      format: form.format,
      language: form.language.trim() || "English",
      base_price: price,
      is_active: Boolean(form.is_active),
    };
    try {
      if (showtime) {
        await api(`/admin/showtimes/${showtime.id}`, { method: "PATCH", body: payload });
        pushToast("Screening updated.", "success");
      } else {
        await api("/admin/showtimes", { method: "POST", body: payload });
        pushToast("Screening added.", "success");
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={showtime ? "Edit screening" : "Schedule a screening"}
      subtitle="Screenings are validated against hall format and overlap rules."
      size="md"
      footer={
        <>
          <button type="button" className="btn btn--ghost btn--sm" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" form="showtime-form" className="btn btn--gold btn--sm" disabled={saving}>
            {saving ? <Spinner size={14} label="Saving" /> : null}{" "}
            {showtime ? "Save changes" : "Schedule"}
          </button>
        </>
      }
    >
      <form id="showtime-form" className="admin-form" onSubmit={submit} noValidate>
        {error ? <div className="inline-banner inline-banner--error">{error}</div> : null}
        <div className="field-grid">
          <label className="field field--full">
            <span>Film</span>
            <select value={form.movie_id} onChange={(event) => update("movie_id", event.target.value)}>
              {movies.map((movie) => (
                <option key={movie.id} value={movie.id}>
                  {movie.title}
                </option>
              ))}
            </select>
            <FieldError>{fieldErrors.movie_id}</FieldError>
          </label>
          <label className="field field--full">
            <span>Hall</span>
            <select value={form.hall_id} onChange={(event) => onHallChange(event.target.value)}>
              {halls.map((hall) => (
                <option key={hall.id} value={hall.id}>
                  {hall.cinema?.name} · {hall.name} ({hall.screen_type})
                </option>
              ))}
            </select>
            <FieldError>{fieldErrors.hall_id}</FieldError>
          </label>
          <label className="field">
            <span>Date &amp; time (Casablanca)</span>
            <input
              type="datetime-local"
              value={form.starts_at}
              onChange={(event) => update("starts_at", event.target.value)}
            />
            <FieldError>{fieldErrors.starts_at}</FieldError>
          </label>
          <label className="field">
            <span>Format</span>
            <select value={form.format} onChange={(event) => update("format", event.target.value)}>
              {formats.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Language</span>
            <input
              value={form.language}
              onChange={(event) => update("language", event.target.value)}
              placeholder="English, French, Arabic…"
            />
          </label>
          <label className="field">
            <span>Base price (MAD)</span>
            <input
              type="number"
              min="1"
              step="0.5"
              value={form.base_price}
              onChange={(event) => update("base_price", event.target.value)}
            />
            <FieldError>{fieldErrors.base_price}</FieldError>
            <small>VIP and VVIP seats apply category multipliers.</small>
          </label>
          {showtime ? (
            <label className="checkbox-field checkbox-field--inline field--full">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => update("is_active", event.target.checked)}
              />
              <span>Published and bookable</span>
            </label>
          ) : null}
        </div>
      </form>
    </Modal>
  );
}

export default function AdminShowtimes() {
  useDocumentTitle("Screenings · Control room");
  const { pushToast } = useToast();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("upcoming");
  const [editor, setEditor] = useState({ open: false, showtime: null });
  const [deactivating, setDeactivating] = useState(null);
  const [saving, setSaving] = useState(false);

  const loader = useCallback(async () => {
    const [showtimes, movies, halls] = await Promise.all([
      api("/admin/showtimes", { params: { limit: 500 } }),
      api("/admin/movies"),
      api("/admin/halls"),
    ]);
    return {
      showtimes: showtimes.items || [],
      movies: (movies.items || []).filter((movie) => movie.status !== "archived"),
      halls: (halls.items || []).filter((hall) => hall.is_active),
    };
  }, []);
  const { data, error, loading, reload } = useApi(loader, []);

  const items = data?.showtimes || [];
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const now = Date.now();
    return items.filter((showtime) => {
      const date = new Date(showtime.starts_at).getTime();
      const stateMatch =
        filter === "all" ||
        (filter === "upcoming" && showtime.is_active && date >= now) ||
        (filter === "past" && date < now) ||
        (filter === "inactive" && !showtime.is_active);
      const queryMatch =
        !needle ||
        showtime.movie_title.toLowerCase().includes(needle) ||
        (showtime.cinema?.name || "").toLowerCase().includes(needle) ||
        (showtime.hall?.name || "").toLowerCase().includes(needle);
      return stateMatch && queryMatch;
    });
  }, [items, query, filter]);

  const counts = useMemo(() => {
    const now = Date.now();
    return {
      all: items.length,
      upcoming: items.filter((item) => item.is_active && new Date(item.starts_at).getTime() >= now).length,
      past: items.filter((item) => new Date(item.starts_at).getTime() < now).length,
      inactive: items.filter((item) => !item.is_active).length,
    };
  }, [items]);

  const deactivate = async () => {
    if (!deactivating) return;
    setSaving(true);
    try {
      await api(`/admin/showtimes/${deactivating.id}`, { method: "DELETE" });
      pushToast("Screening unpublished.", "success");
      setDeactivating(null);
      reload();
    } catch (err) {
      pushToast(apiErrorMessage(err), "error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <PageLoader label="Loading the screening grid" />;
  if (error) return <ErrorState error={error} onRetry={() => reload(true)} title="Screenings are hiding" />;

  return (
    <div className="admin-page">
      <AdminPageHead
        eyebrow="Programme"
        title="Screenings"
        description="The calendar across all three houses. Overlaps and formats are validated by the movie service."
        actions={
          <button
            type="button"
            className="btn btn--gold btn--sm"
            onClick={() => setEditor({ open: true, showtime: null })}
          >
            <CalendarPlus size={14} /> New screening
          </button>
        }
      />

      <div className="admin-toolbar">
        <div className="segmented" role="tablist" aria-label="Screening filters">
          {[
            ["upcoming", "Upcoming"],
            ["past", "Past"],
            ["inactive", "Unpublished"],
            ["all", "All"],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={filter === value}
              className={filter === value ? "is-active" : ""}
              onClick={() => setFilter(value)}
            >
              {label} <span>{counts[value]}</span>
            </button>
          ))}
        </div>
        <AdminSearch value={query} onChange={setQuery} placeholder="Film, cinema or hall" />
      </div>

      {filtered.length ? (
        <div className="admin-table-wrap">
          <table className="admin-table admin-table--showtimes">
            <thead>
              <tr>
                <th>When</th>
                <th>Film</th>
                <th>House</th>
                <th>Format</th>
                <th>Language</th>
                <th>Base price</th>
                <th>Status</th>
                <th className="align-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 200).map((showtime) => (
                <tr key={showtime.id}>
                  <td>
                    <strong>{showtime.time}</strong>
                    <small className="table-sub">{formatDateLong(showtime.starts_at)}</small>
                  </td>
                  <td>
                    <div className="table-title-cell">
                      <Clapperboard size={14} />
                      <span>{showtime.movie_title}</span>
                    </div>
                  </td>
                  <td>
                    {showtime.cinema?.name}
                    <small className="table-sub">{showtime.hall?.name}</small>
                  </td>
                  <td>
                    <span className="format-pill">{showtime.format_label}</span>
                  </td>
                  <td>{showtime.language}</td>
                  <td>{money(showtime.base_price, showtime.currency)}</td>
                  <td>
                    <StatusPill status={showtime.is_active} />
                  </td>
                  <td>
                    <div className="table-actions">
                      <button
                        type="button"
                        className="icon-btn"
                        onClick={() => setEditor({ open: true, showtime })}
                        aria-label="Edit screening"
                        title="Edit screening"
                      >
                        <Pencil size={15} />
                      </button>
                      {showtime.is_active ? (
                        <button
                          type="button"
                          className="icon-btn icon-btn--danger"
                          onClick={() => setDeactivating(showtime)}
                          aria-label="Unpublish screening"
                          title="Unpublish screening"
                        >
                          <Power size={15} />
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <AdminEmpty
          icon={CalendarRange}
          title="No screenings here"
          message="Change the filter, or schedule a new screening."
          action={
            <button
              type="button"
              className="btn btn--gold btn--sm"
              onClick={() => setEditor({ open: true, showtime: null })}
            >
              <CalendarPlus size={14} /> New screening
            </button>
          }
        />
      )}

      {filtered.length > 200 ? (
        <p className="admin-muted admin-table-note">
          Showing the first 200 of {filtered.length} screenings. Narrow the filter to see more.
        </p>
      ) : null}

      <div className="admin-note-row">
        <Search size={15} />
        <span>
          A screening must sit inside the hall's supported formats and leave a 20-minute turnover.
        </span>
        <span className="admin-note-price">{counts.upcoming} bookable</span>
      </div>

      {editor.open ? (
        <ShowtimeForm
          key={editor.showtime?.id || "new"}
          open={editor.open}
          showtime={editor.showtime}
          movies={data?.movies || []}
          halls={data?.halls || []}
          onClose={() => setEditor({ open: false, showtime: null })}
          onSaved={() => reload()}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(deactivating)}
        onClose={() => setDeactivating(null)}
        onConfirm={deactivate}
        busy={saving}
        title="Unpublish this screening?"
        message={`${deactivating?.movie_title || "This film"} at ${deactivating?.time || ""} will disappear from the public programme. Existing bookings remain valid.`}
        confirmLabel="Unpublish"
      />
    </div>
  );
}
