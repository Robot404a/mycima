import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Armchair,
  Building2,
  MapPin,
  Palette,
  Pencil,
  Plus,
  ScreenShare,
  Sparkles,
} from "lucide-react";
import { api, apiErrorMessage } from "../../lib/api";
import { useApi, useDocumentTitle } from "../../lib/hooks";
import { ErrorState, PageLoader, Spinner } from "../../components/Feedback";
import { Modal } from "../../components/Modal";
import { useToast } from "../../context/ToastContext";
import {
  AdminEmpty,
  AdminPageHead,
  FieldError,
  MiniStat,
} from "./ui";

const CATEGORIES = [
  ["REGULAR", "Regular", "×1.0"],
  ["VIP", "VIP", "×1.5"],
  ["VVIP", "VVIP", "×2.2"],
];
const FORMATS = [
  ["STANDARD", "2D"],
  ["THREE_D", "3D"],
  ["IMAX", "IMAX"],
];
const emptyCinema = { name: "", address: "", city: "Casablanca", description: "", amenities: "" };

function CinemaForm({ open, onClose, onSaved }) {
  const { pushToast } = useToast();
  const [form, setForm] = useState(emptyCinema);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const submit = async (event) => {
    event.preventDefault();
    if (saving) return;
    if (!form.name.trim() || !form.address.trim() || !form.city.trim()) {
      setError("Name, address and city are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api("/admin/cinemas", {
        method: "POST",
        body: {
          name: form.name.trim(),
          address: form.address.trim(),
          city: form.city.trim(),
          description: form.description.trim() || null,
          amenities: form.amenities
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
        },
      });
      pushToast("Cinema added.", "success");
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
      title="Add a cinema"
      subtitle="A new house appears in the public programme once it has an active hall."
      size="md"
      footer={
        <>
          <button type="button" className="btn btn--ghost btn--sm" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" form="cinema-form" className="btn btn--gold btn--sm" disabled={saving}>
            {saving ? <Spinner size={14} label="Saving" /> : null} Add cinema
          </button>
        </>
      }
    >
      <form id="cinema-form" className="admin-form" onSubmit={submit} noValidate>
        {error ? <div className="inline-banner inline-banner--error">{error}</div> : null}
        <div className="field-grid">
          <label className="field field--full">
            <span>Name</span>
            <input value={form.name} onChange={(event) => update("name", event.target.value)} placeholder="MyCima …" />
          </label>
          <label className="field field--full">
            <span>Address</span>
            <input value={form.address} onChange={(event) => update("address", event.target.value)} placeholder="Street, district" />
          </label>
          <label className="field">
            <span>City</span>
            <input value={form.city} onChange={(event) => update("city", event.target.value)} />
          </label>
          <label className="field">
            <span>Amenities</span>
            <input
              value={form.amenities}
              onChange={(event) => update("amenities", event.target.value)}
              placeholder="Bar, Parking"
            />
          </label>
          <label className="field field--full">
            <span>Description</span>
            <textarea
              rows={3}
              value={form.description}
              onChange={(event) => update("description", event.target.value)}
              placeholder="The character of the house."
            />
          </label>
        </div>
      </form>
    </Modal>
  );
}

function HallForm({ open, onClose, hall, cinemas, preselectedCinema, onSaved }) {
  const { pushToast } = useToast();
  const [form, setForm] = useState(() =>
    hall
      ? {
          cinema_id: String(hall.cinema_id),
          name: hall.name,
          screen_type: hall.screen_type,
          row_count: String(hall.row_count),
          seats_per_row: String(hall.seats_per_row),
          aisles_after: (hall.aisles_after || []).join(", "),
          supported_formats: hall.supported_formats || ["STANDARD"],
          description: hall.description || "",
          is_active: hall.is_active,
        }
      : {
          cinema_id: String(preselectedCinema || cinemas[0]?.id || ""),
          name: "",
          screen_type: "Standard",
          row_count: "10",
          seats_per_row: "14",
          aisles_after: "4, 10",
          supported_formats: ["STANDARD"],
          description: "",
          is_active: true,
        },
  );
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const toggleFormat = (value) => {
    setForm((current) => {
      const exists = current.supported_formats.includes(value);
      const next = exists
        ? current.supported_formats.filter((item) => item !== value)
        : [...current.supported_formats, value];
      return { ...current, supported_formats: next.length ? next : [value] };
    });
  };

  const submit = async (event) => {
    event.preventDefault();
    if (saving) return;
    const errors = {};
    if (!form.name.trim()) errors.name = "Give the hall a name.";
    if (!form.cinema_id) errors.cinema_id = "Choose a cinema.";
    const rows = Number(form.row_count);
    const perRow = Number(form.seats_per_row);
    if (!hall) {
      if (!Number.isInteger(rows) || rows < 3 || rows > 30) errors.row_count = "Between 3 and 30 rows.";
      if (!Number.isInteger(perRow) || perRow < 4 || perRow > 40) {
        errors.seats_per_row = "Between 4 and 40 seats per row.";
      }
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;
    setSaving(true);
    setError("");
    try {
      if (hall) {
        await api(`/admin/halls/${hall.id}`, {
          method: "PATCH",
          body: {
            name: form.name.trim(),
            screen_type: form.screen_type.trim() || "Standard",
            supported_formats: form.supported_formats,
            description: form.description.trim() || null,
            is_active: Boolean(form.is_active),
          },
        });
        pushToast("Hall updated.", "success");
      } else {
        await api("/admin/halls", {
          method: "POST",
          body: {
            cinema_id: Number(form.cinema_id),
            name: form.name.trim(),
            screen_type: form.screen_type.trim() || "Standard",
            row_count: rows,
            seats_per_row: perRow,
            aisles_after: form.aisles_after
              .split(",")
              .map((item) => Number(item.trim()))
              .filter((item) => Number.isInteger(item) && item > 0 && item < perRow),
            supported_formats: form.supported_formats,
            description: form.description.trim() || null,
          },
        });
        pushToast("Hall added with a full seat map.", "success");
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
      title={hall ? `Edit ${hall.name}` : "Add a hall"}
      subtitle={
        hall
          ? "Row count and seat geometry are fixed once a hall exists."
          : "Seat categories are generated automatically and can be tuned afterwards."
      }
      size="md"
      footer={
        <>
          <button type="button" className="btn btn--ghost btn--sm" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" form="hall-form" className="btn btn--gold btn--sm" disabled={saving}>
            {saving ? <Spinner size={14} label="Saving" /> : null} {hall ? "Save changes" : "Add hall"}
          </button>
        </>
      }
    >
      <form id="hall-form" className="admin-form" onSubmit={submit} noValidate>
        {error ? <div className="inline-banner inline-banner--error">{error}</div> : null}
        <div className="field-grid">
          <label className="field field--full">
            <span>Cinema</span>
            <select
              value={form.cinema_id}
              onChange={(event) => update("cinema_id", event.target.value)}
              disabled={Boolean(hall)}
            >
              {cinemas.map((cinema) => (
                <option key={cinema.id} value={cinema.id}>
                  {cinema.name} · {cinema.city}
                </option>
              ))}
            </select>
            <FieldError>{fieldErrors.cinema_id}</FieldError>
          </label>
          <label className="field">
            <span>Hall name</span>
            <input value={form.name} onChange={(event) => update("name", event.target.value)} placeholder="Salle Lumière" />
            <FieldError>{fieldErrors.name}</FieldError>
          </label>
          <label className="field">
            <span>Screen type</span>
            <input
              value={form.screen_type}
              onChange={(event) => update("screen_type", event.target.value)}
              placeholder="IMAX, Dolby, 35mm…"
            />
          </label>
          <label className="field">
            <span>Rows</span>
            <input
              type="number"
              min="3"
              max="30"
              value={form.row_count}
              onChange={(event) => update("row_count", event.target.value)}
              disabled={Boolean(hall)}
            />
            <FieldError>{fieldErrors.row_count}</FieldError>
          </label>
          <label className="field">
            <span>Seats per row</span>
            <input
              type="number"
              min="4"
              max="40"
              value={form.seats_per_row}
              onChange={(event) => update("seats_per_row", event.target.value)}
              disabled={Boolean(hall)}
            />
            <FieldError>{fieldErrors.seats_per_row}</FieldError>
          </label>
          <label className="field field--full">
            <span>Aisles after seat</span>
            <input
              value={form.aisles_after}
              onChange={(event) => update("aisles_after", event.target.value)}
              disabled={Boolean(hall)}
              placeholder="4, 10"
            />
            <small>Comma separated seat numbers. Creates a visual gap in the hall.</small>
          </label>
          <div className="field field--full">
            <span>Supported formats</span>
            <div className="format-checklist">
              {FORMATS.map(([value, label]) => (
                <label key={value} className="checkbox-field checkbox-field--inline">
                  <input
                    type="checkbox"
                    checked={form.supported_formats.includes(value)}
                    onChange={() => toggleFormat(value)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </div>
          <label className="field field--full">
            <span>Description</span>
            <textarea
              rows={2}
              value={form.description}
              onChange={(event) => update("description", event.target.value)}
              placeholder="What makes this room special."
            />
          </label>
          {hall ? (
            <label className="checkbox-field checkbox-field--inline field--full">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => update("is_active", event.target.checked)}
              />
              <span>Active and visible in the programme</span>
            </label>
          ) : null}
        </div>
      </form>
    </Modal>
  );
}

function SeatEditor({ hall, onHallChanged }) {
  const { pushToast } = useToast();
  const [painting, setPainting] = useState("VIP");
  const [pending, setPending] = useState(new Set());

  const loader = useCallback(() => api(`/admin/halls/${hall.id}/layout`), [hall.id]);
  const { data, error, loading, setData } = useApi(loader, [hall.id]);

  const seats = data?.seats || [];
  const rows = useMemo(() => {
    const grouped = new Map();
    for (const seat of seats) {
      if (!grouped.has(seat.row_label)) grouped.set(seat.row_label, []);
      grouped.get(seat.row_label).push(seat);
    }
    return [...grouped.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([label, rowSeats]) => [label, rowSeats.sort((a, b) => a.seat_number - b.seat_number)]);
  }, [seats]);

  const aisleSet = useMemo(
    () => new Set((data?.hall?.aisles_after || hall.aisles_after || []).map(Number)),
    [data?.hall, hall.aisles_after],
  );

  const counts = useMemo(() => {
    const result = { REGULAR: 0, VIP: 0, VVIP: 0 };
    seats.forEach((seat) => {
      result[seat.category] = (result[seat.category] || 0) + 1;
    });
    return result;
  }, [seats]);

  const paintSeat = async (seat) => {
    if (pending.has(seat.seat_id) || seat.category === painting) return;
    const previous = seat.category;
    setPending((current) => new Set(current).add(seat.seat_id));
    setData((current) =>
      current
        ? {
            ...current,
            seats: current.seats.map((entry) =>
              entry.seat_id === seat.seat_id ? { ...entry, category: painting } : entry,
            ),
          }
        : current,
    );
    try {
      await api(`/admin/halls/${hall.id}/seats/${seat.seat_id}`, {
        method: "PATCH",
        body: { category: painting },
      });
      onHallChanged?.();
    } catch (err) {
      setData((current) =>
        current
          ? {
              ...current,
              seats: current.seats.map((entry) =>
                entry.seat_id === seat.seat_id ? { ...entry, category: previous } : entry,
              ),
            }
          : current,
      );
      pushToast(apiErrorMessage(err), "error");
    } finally {
      setPending((current) => {
        const next = new Set(current);
        next.delete(seat.seat_id);
        return next;
      });
    }
  };

  if (loading) {
    return (
      <div className="hall-editor-loading">
        <Spinner size={20} label="Loading hall layout" /> Loading the seat map…
      </div>
    );
  }
  if (error) return <ErrorState error={error} title="The hall layout could not be loaded" />;

  return (
    <div className="hall-editor">
      <div className="hall-editor-head">
        <div>
          <span className="eyebrow">Seat editor</span>
          <h2>{hall.name}</h2>
          <p>
            {data?.cinema?.name} · {hall.row_count} rows · {seats.length} seats ·{" "}
            {(hall.supported_formats || []).join(" / ")}
          </p>
        </div>
        <div className="hall-editor-legend">
          {CATEGORIES.map(([value, label]) => (
            <span key={value} className={`category-legend category-legend--${value.toLowerCase()}`}>
              <i /> {label} <small>{counts[value] || 0}</small>
            </span>
          ))}
        </div>
      </div>

      <div className="paint-toolbar" role="group" aria-label="Seat category to paint">
        <span className="paint-label">
          <Palette size={15} /> Paint as
        </span>
        {CATEGORIES.map(([value, label, multiplier]) => (
          <button
            key={value}
            type="button"
            className={`paint-btn paint-btn--${value.toLowerCase()} ${painting === value ? "is-active" : ""}`}
            onClick={() => setPainting(value)}
            aria-pressed={painting === value}
          >
            {label} <small>{multiplier}</small>
          </button>
        ))}
      </div>

      <div className="hall-screen-line" aria-hidden="true">
        <span>SCREEN</span>
      </div>

      <div className="hall-seat-map" role="group" aria-label={`Seat categories for ${hall.name}`}>
        {rows.map(([label, rowSeats]) => (
          <div className="hall-seat-row" key={label}>
            <span className="hall-row-label">{label}</span>
            <div className="hall-seat-row-seats">
              {rowSeats.map((seat) => {
                const isPending = pending.has(seat.seat_id);
                return (
                  <span key={seat.seat_id} className="hall-seat-wrap">
                    <button
                      type="button"
                      className={`hall-seat hall-seat--${seat.category.toLowerCase()} ${
                        seat.category === painting ? "is-painted" : ""
                      } ${isPending ? "is-pending" : ""}`}
                      onClick={() => paintSeat(seat)}
                      aria-label={`Seat ${seat.seat_id}, ${seat.category}. Paint as ${painting}.`}
                      title={`${seat.seat_id} · ${seat.category}`}
                    >
                      {seat.seat_number}
                    </button>
                    {aisleSet.has(seat.seat_number) ? <span className="hall-aisle" /> : null}
                  </span>
                );
              })}
            </div>
            <span className="hall-row-label">{label}</span>
          </div>
        ))}
      </div>

      <p className="hall-editor-note">
        <Sparkles size={14} /> Categories set the price multiplier: Regular ×1.0, VIP ×1.5, VVIP
        ×2.2. Changes apply to future bookings; existing snapshots keep their price.
      </p>
    </div>
  );
}

export default function AdminHalls() {
  useDocumentTitle("Halls & seats · Control room");
  const [selectedHallId, setSelectedHallId] = useState(null);
  const [cinemaFormOpen, setCinemaFormOpen] = useState(false);
  const [hallEditor, setHallEditor] = useState({ open: false, hall: null });

  const loader = useCallback(async () => {
    const [cinemas, halls] = await Promise.all([api("/admin/cinemas"), api("/admin/halls")]);
    return { cinemas: cinemas.items || [], halls: halls.items || [] };
  }, []);
  const { data, error, loading, reload } = useApi(loader, []);

  const cinemas = data?.cinemas || [];
  const halls = data?.halls || [];
  const selectedHall = halls.find((hall) => hall.id === selectedHallId) || halls[0] || null;

  useEffect(() => {
    if (!selectedHallId && halls.length) setSelectedHallId(halls[0].id);
  }, [halls, selectedHallId]);

  const totals = useMemo(
    () => ({
      cinemas: cinemas.length,
      halls: halls.length,
      seats: halls.reduce((sum, hall) => sum + Number(hall.row_count) * Number(hall.seats_per_row), 0),
      screens: new Set(halls.map((hall) => hall.screen_type)).size,
    }),
    [cinemas, halls],
  );

  const hallsByCinema = useMemo(() => {
    const grouped = new Map();
    for (const cinema of cinemas) grouped.set(cinema.id, []);
    for (const hall of halls) {
      if (!grouped.has(hall.cinema_id)) grouped.set(hall.cinema_id, []);
      grouped.get(hall.cinema_id).push(hall);
    }
    return grouped;
  }, [cinemas, halls]);

  if (loading) return <PageLoader label="Walking the halls" />;
  if (error) return <ErrorState error={error} onRetry={() => reload(true)} title="The halls are dark" />;

  return (
    <div className="admin-page">
      <AdminPageHead
        eyebrow="Venues"
        title="Halls & seats"
        description="The physical rooms, their formats and the category of every seat."
        actions={
          <>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setCinemaFormOpen(true)}>
              <Building2 size={14} /> Add cinema
            </button>
            <button
              type="button"
              className="btn btn--gold btn--sm"
              onClick={() => setHallEditor({ open: true, hall: null })}
            >
              <Plus size={14} /> Add hall
            </button>
          </>
        }
      />

      <div className="venue-stats">
        <MiniStat label="Cinemas" value={totals.cinemas} hint="Across Casablanca" />
        <MiniStat label="Halls" value={totals.halls} hint="Screens in the group" />
        <MiniStat label="Seats" value={totals.seats.toLocaleString("en-GB")} hint="Physical seats" />
        <MiniStat label="Screen types" value={totals.screens} hint="Standard, IMAX, Dolby…" />
      </div>

      <div className="halls-layout">
        <aside className="venue-panel">
          <div className="admin-card-head">
            <div>
              <span className="eyebrow">Houses</span>
              <h2>Cinemas &amp; halls</h2>
            </div>
          </div>
          {cinemas.length ? (
            <div className="venue-list">
              {cinemas.map((cinema) => (
                <div key={cinema.id} className="venue-group">
                  <div className="venue-group-head">
                    <span className="venue-group-icon">
                      <Building2 size={16} />
                    </span>
                    <div>
                      <strong>{cinema.name}</strong>
                      <small>
                        <MapPin size={11} /> {cinema.address}, {cinema.city}
                      </small>
                    </div>
                  </div>
                  <div className="venue-hall-list">
                    {(hallsByCinema.get(cinema.id) || []).map((hall) => (
                      <button
                        key={hall.id}
                        type="button"
                        className={`venue-hall ${selectedHall?.id === hall.id ? "is-active" : ""} ${
                          !hall.is_active ? "is-inactive" : ""
                        }`}
                        onClick={() => setSelectedHallId(hall.id)}
                      >
                        <span className="venue-hall-name">
                          {hall.name}
                          {!hall.is_active ? <small> (inactive)</small> : null}
                        </span>
                        <span className="venue-hall-meta">
                          {hall.screen_type} · {hall.row_count}×{hall.seats_per_row}
                        </span>
                        <Pencil size={13} />
                      </button>
                    ))}
                    {!(hallsByCinema.get(cinema.id) || []).length ? (
                      <p className="venue-empty">No halls yet.</p>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <AdminEmpty
              icon={Building2}
              title="No cinemas yet"
              message="Add the first house to start scheduling screenings."
            />
          )}
        </aside>

        <section className="venue-editor">
          {selectedHall ? (
            <>
              <div className="venue-editor-actions">
                <div>
                  <span className="venue-format-chips">
                    {(selectedHall.supported_formats || []).map((format) => (
                      <span key={format} className="format-pill">
                        {FORMATS.find(([value]) => value === format)?.[1] || format}
                      </span>
                    ))}
                  </span>
                </div>
                <button
                  type="button"
                  className="btn btn--ghost btn--sm"
                  onClick={() => setHallEditor({ open: true, hall: selectedHall })}
                >
                  <Pencil size={14} /> Edit hall
                </button>
              </div>
              <SeatEditor hall={selectedHall} onHallChanged={() => reload()} />
            </>
          ) : (
            <AdminEmpty
              icon={Armchair}
              title="Choose a hall"
              message="Add a cinema and a hall to begin shaping the seat map."
              action={
                <button
                  type="button"
                  className="btn btn--gold btn--sm"
                  onClick={() => setHallEditor({ open: true, hall: null })}
                >
                  <Plus size={14} /> Add hall
                </button>
              }
            />
          )}
        </section>
      </div>

      <div className="admin-note-row">
        <ScreenShare size={15} />
        <span>
          New halls generate a full seat grid automatically. Aisles only change the visual gap, not
          the seat numbering.
        </span>
        <span className="admin-note-price">
          {totals.seats.toLocaleString("en-GB")} seats managed
        </span>
      </div>

      {cinemaFormOpen ? (
        <CinemaForm
          open={cinemaFormOpen}
          onClose={() => setCinemaFormOpen(false)}
          onSaved={() => reload()}
        />
      ) : null}

      {hallEditor.open ? (
        <HallForm
          key={hallEditor.hall?.id || "new"}
          open={hallEditor.open}
          hall={hallEditor.hall}
          cinemas={cinemas}
          preselectedCinema={selectedHall?.cinema_id}
          onClose={() => setHallEditor({ open: false, hall: null })}
          onSaved={() => reload()}
        />
      ) : null}
    </div>
  );
}
