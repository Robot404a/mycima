import { useCallback, useMemo, useState } from "react";
import {
  Clapperboard,
  Film,
  Pencil,
  Plus,
  Star,
  Trash2,
} from "lucide-react";
import { api, apiErrorMessage } from "../../lib/api";
import { useApi, useDocumentTitle } from "../../lib/hooks";
import { duration, formatDateShort } from "../../lib/format";
import { ErrorState, PageLoader, Poster, Spinner } from "../../components/Feedback";
import { Modal } from "../../components/Modal";
import { useToast } from "../../context/ToastContext";
import {
  AdminEmpty,
  AdminPageHead,
  AdminSearch,
  FieldError,
  StatusPill,
  ConfirmDialog,
} from "./ui";

const EMPTY = {
  title: "",
  tagline: "",
  synopsis: "",
  genres: "",
  duration_min: "105",
  age_rating: "PG-13",
  director: "",
  cast: "",
  release_date: "",
  poster_url: "",
  backdrop_url: "",
  trailer_url: "",
  status: "now_showing",
  featured: false,
  mood_tags: "",
  rating: "",
};

const splitCsv = (value) =>
  String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

function toForm(movie) {
  if (!movie) return { ...EMPTY };
  return {
    title: movie.title || "",
    tagline: movie.tagline || "",
    synopsis: movie.synopsis || "",
    genres: (movie.genres || []).join(", "),
    duration_min: String(movie.duration_min || ""),
    age_rating: movie.age_rating || "PG-13",
    director: movie.director || "",
    cast: (movie.cast || []).join(", "),
    release_date: movie.release_date || "",
    poster_url: movie.poster_url || "",
    backdrop_url: movie.backdrop_url || "",
    trailer_url: movie.trailer_url || "",
    status: movie.status || "now_showing",
    featured: Boolean(movie.featured),
    mood_tags: (movie.mood_tags || []).join(", "),
    rating: movie.rating != null ? String(movie.rating) : "",
  };
}

function MovieForm({ open, onClose, movie, onSaved }) {
  const { pushToast } = useToast();
  const [form, setForm] = useState(() => toForm(movie));
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const submit = async (event) => {
    event.preventDefault();
    if (saving) return;
    const errors = {};
    if (!form.title.trim()) errors.title = "A title is required.";
    if (form.synopsis.trim().length < 10) errors.synopsis = "Write at least 10 characters.";
    const minutes = Number(form.duration_min);
    if (!Number.isFinite(minutes) || minutes < 20 || minutes > 400) {
      errors.duration_min = "Between 20 and 400 minutes.";
    }
    if (!form.poster_url.trim()) errors.poster_url = "A poster URL is required.";
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;
    setError("");
    setSaving(true);
    const payload = {
      title: form.title.trim(),
      tagline: form.tagline.trim() || null,
      synopsis: form.synopsis.trim(),
      genres: splitCsv(form.genres),
      duration_min: minutes,
      age_rating: form.age_rating.trim() || "PG",
      director: form.director.trim() || null,
      cast: splitCsv(form.cast),
      release_date: form.release_date || null,
      poster_url: form.poster_url.trim(),
      backdrop_url: form.backdrop_url.trim() || null,
      trailer_url: form.trailer_url.trim() || null,
      status: form.status,
      featured: Boolean(form.featured),
      mood_tags: splitCsv(form.mood_tags),
      rating: form.rating === "" ? null : Number(form.rating),
    };
    try {
      if (movie) {
        await api(`/admin/movies/${movie.id}`, { method: "PATCH", body: payload });
        pushToast("Film updated.", "success");
      } else {
        await api("/admin/movies", { method: "POST", body: payload });
        pushToast("Film added to the catalogue.", "success");
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
      title={movie ? `Edit ${movie.title}` : "Add a film"}
      subtitle={
        movie
          ? "Changes appear on the public programme immediately."
          : "New films join the catalogue as soon as you save them."
      }
      size="lg"
      footer={
        <>
          <button type="button" className="btn btn--ghost btn--sm" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" form="movie-form" className="btn btn--gold btn--sm" disabled={saving}>
            {saving ? <Spinner size={14} label="Saving" /> : null} {movie ? "Save changes" : "Add film"}
          </button>
        </>
      }
    >
      <form id="movie-form" className="admin-form" onSubmit={submit} noValidate>
        {error ? <div className="inline-banner inline-banner--error">{error}</div> : null}
        <div className="field-grid">
          <label className="field field--full">
            <span>Title</span>
            <input
              value={form.title}
              onChange={(event) => update("title", event.target.value)}
              placeholder="Film title"
            />
            <FieldError>{fieldErrors.title}</FieldError>
          </label>
          <label className="field field--full">
            <span>Tagline</span>
            <input
              value={form.tagline}
              onChange={(event) => update("tagline", event.target.value)}
              placeholder="One line that stays with you"
            />
          </label>
          <label className="field field--full">
            <span>Synopsis</span>
            <textarea
              rows={4}
              value={form.synopsis}
              onChange={(event) => update("synopsis", event.target.value)}
              placeholder="What happens, without spoilers."
            />
            <FieldError>{fieldErrors.synopsis}</FieldError>
          </label>
          <label className="field">
            <span>Genres</span>
            <input
              value={form.genres}
              onChange={(event) => update("genres", event.target.value)}
              placeholder="Drama, Sci-Fi"
            />
            <small>Comma separated.</small>
          </label>
          <label className="field">
            <span>Mood tags</span>
            <input
              value={form.mood_tags}
              onChange={(event) => update("mood_tags", event.target.value)}
              placeholder="thoughtful, epic"
            />
            <small>Comma separated.</small>
          </label>
          <label className="field">
            <span>Duration (minutes)</span>
            <input
              type="number"
              min="20"
              max="400"
              value={form.duration_min}
              onChange={(event) => update("duration_min", event.target.value)}
            />
            <FieldError>{fieldErrors.duration_min}</FieldError>
          </label>
          <label className="field">
            <span>Age rating</span>
            <input
              value={form.age_rating}
              onChange={(event) => update("age_rating", event.target.value)}
              placeholder="PG-13"
            />
          </label>
          <label className="field">
            <span>Director</span>
            <input
              value={form.director}
              onChange={(event) => update("director", event.target.value)}
              placeholder="Director name"
            />
          </label>
          <label className="field">
            <span>Cast</span>
            <input
              value={form.cast}
              onChange={(event) => update("cast", event.target.value)}
              placeholder="Actor, Actor, Actor"
            />
          </label>
          <label className="field">
            <span>Release date</span>
            <input
              type="date"
              value={form.release_date}
              onChange={(event) => update("release_date", event.target.value)}
            />
          </label>
          <label className="field">
            <span>Rating</span>
            <input
              type="number"
              step="0.1"
              min="0"
              max="10"
              value={form.rating}
              onChange={(event) => update("rating", event.target.value)}
              placeholder="8.4"
            />
          </label>
          <label className="field field--full">
            <span>Poster URL</span>
            <input
              value={form.poster_url}
              onChange={(event) => update("poster_url", event.target.value)}
              placeholder="/media/posters/film.jpg"
            />
            <FieldError>{fieldErrors.poster_url}</FieldError>
            <small>Relative media paths and absolute URLs both work.</small>
          </label>
          <label className="field field--full">
            <span>Backdrop URL</span>
            <input
              value={form.backdrop_url}
              onChange={(event) => update("backdrop_url", event.target.value)}
              placeholder="Optional wide image"
            />
          </label>
          <label className="field field--full">
            <span>Trailer URL</span>
            <input
              value={form.trailer_url}
              onChange={(event) => update("trailer_url", event.target.value)}
              placeholder="https://…"
            />
          </label>
          <label className="field">
            <span>Status</span>
            <select value={form.status} onChange={(event) => update("status", event.target.value)}>
              <option value="now_showing">Now showing</option>
              <option value="coming_soon">Coming soon</option>
              <option value="archived">Archived</option>
            </select>
          </label>
          <label className="checkbox-field checkbox-field--inline">
            <input
              type="checkbox"
              checked={form.featured}
              onChange={(event) => update("featured", event.target.checked)}
            />
            <span>Feature on the landing shelf</span>
          </label>
        </div>
      </form>
    </Modal>
  );
}

export default function AdminMovies() {
  useDocumentTitle("Films · Control room");
  const { pushToast } = useToast();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [editor, setEditor] = useState({ open: false, movie: null });
  const [archiving, setArchiving] = useState(null);
  const [saving, setSaving] = useState(false);

  const loader = useCallback(() => api("/admin/movies"), []);
  const { data, error, loading, reload } = useApi(loader, []);

  const items = data?.items || [];
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items.filter((movie) => {
      const statusMatch = status === "all" || movie.status === status;
      const queryMatch =
        !needle ||
        movie.title.toLowerCase().includes(needle) ||
        (movie.genres || []).join(" ").toLowerCase().includes(needle) ||
        (movie.director || "").toLowerCase().includes(needle);
      return statusMatch && queryMatch;
    });
  }, [items, query, status]);

  const counts = useMemo(
    () => ({
      all: items.length,
      now_showing: items.filter((movie) => movie.status === "now_showing").length,
      coming_soon: items.filter((movie) => movie.status === "coming_soon").length,
      archived: items.filter((movie) => movie.status === "archived").length,
    }),
    [items],
  );

  const archive = async () => {
    if (!archiving) return;
    setSaving(true);
    try {
      await api(`/admin/movies/${archiving.id}`, { method: "PATCH", body: { status: "archived" } });
      pushToast(`${archiving.title} archived.`, "success");
      setArchiving(null);
      reload();
    } catch (err) {
      pushToast(apiErrorMessage(err), "error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <PageLoader label="Loading the catalogue" />;
  if (error) return <ErrorState error={error} onRetry={() => reload(true)} title="The catalogue is hiding" />;

  return (
    <div className="admin-page">
      <AdminPageHead
        eyebrow="Catalogue"
        title="Films"
        description="The programme, the shelf and everything the concierge can recommend."
        actions={
          <button
            type="button"
            className="btn btn--gold btn--sm"
            onClick={() => setEditor({ open: true, movie: null })}
          >
            <Plus size={14} /> Add film
          </button>
        }
      />

      <div className="admin-toolbar">
        <div className="segmented" role="tablist" aria-label="Film status">
          {[
            ["all", "All"],
            ["now_showing", "Now showing"],
            ["coming_soon", "Coming soon"],
            ["archived", "Archived"],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={status === value}
              className={status === value ? "is-active" : ""}
              onClick={() => setStatus(value)}
            >
              {label} <span>{counts[value]}</span>
            </button>
          ))}
        </div>
        <AdminSearch value={query} onChange={setQuery} placeholder="Search title, genre or director" />
      </div>

      {filtered.length ? (
        <div className="admin-table-wrap">
          <table className="admin-table admin-table--movies">
            <thead>
              <tr>
                <th>Film</th>
                <th>Status</th>
                <th>Genre</th>
                <th>Runtime</th>
                <th>Rating</th>
                <th>Release</th>
                <th className="align-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((movie) => (
                <tr key={movie.id}>
                  <td>
                    <div className="table-film-cell">
                      <div className="table-poster">
                        <Poster src={movie.poster_url} title={movie.title} />
                      </div>
                      <div>
                        <strong>{movie.title}</strong>
                        <small>{movie.tagline || movie.director || "—"}</small>
                        {movie.featured ? (
                          <span className="featured-tag">
                            <Star size={10} fill="currentColor" /> Featured
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </td>
                  <td>
                    <StatusPill status={movie.status} />
                  </td>
                  <td>
                    <span className="table-genres">{(movie.genres || []).slice(0, 2).join(" · ") || "—"}</span>
                  </td>
                  <td>{duration(movie.duration_min)}</td>
                  <td>{movie.rating ? Number(movie.rating).toFixed(1) : "—"}</td>
                  <td>{movie.release_date ? formatDateShort(movie.release_date) : "—"}</td>
                  <td>
                    <div className="table-actions">
                      <button
                        type="button"
                        className="icon-btn"
                        onClick={() => setEditor({ open: true, movie })}
                        aria-label={`Edit ${movie.title}`}
                        title="Edit film"
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        type="button"
                        className="icon-btn icon-btn--danger"
                        onClick={() => setArchiving(movie)}
                        aria-label={`Archive ${movie.title}`}
                        title="Archive film"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <AdminEmpty
          icon={Film}
          title="No films in this cut"
          message="Change the filter, or add a film to the catalogue."
          action={
            <button
              type="button"
              className="btn btn--gold btn--sm"
              onClick={() => setEditor({ open: true, movie: null })}
            >
              <Plus size={14} /> Add film
            </button>
          }
        />
      )}

      <div className="admin-note-row">
        <Clapperboard size={15} />
        <span>
          Archiving hides a film from the public catalogue. Existing bookings keep their snapshot.
        </span>
        <span className="admin-note-price">
          {items.length} films · {counts.now_showing} on screen
        </span>
      </div>

      {editor.open ? (
        <MovieForm
          key={editor.movie?.id || "new"}
          open={editor.open}
          movie={editor.movie}
          onClose={() => setEditor({ open: false, movie: null })}
          onSaved={() => reload()}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(archiving)}
        onClose={() => setArchiving(null)}
        onConfirm={archive}
        busy={saving}
        title="Archive this film?"
        message={`${archiving?.title || "This film"} will disappear from the public programme. Existing tickets are unaffected.`}
        confirmLabel="Archive film"
      />
    </div>
  );
}
