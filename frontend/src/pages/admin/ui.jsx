import { Search } from "lucide-react";
import { EmptyState, Spinner, Skeleton } from "../../components/Feedback";
import { Modal } from "../../components/Modal";

const STATUS_LABELS = {
  CONFIRMED: "Confirmed",
  CANCELLED: "Cancelled",
  ACTIVE: "Active",
  EXPIRED: "Expired",
  CANCELLING: "Cancelling",
  CONFIRMING: "Confirming",
  PAYMENT_FAILED: "Payment failed",
  now_showing: "Now showing",
  coming_soon: "Coming soon",
  archived: "Archived",
  true: "Active",
  false: "Inactive",
};

export function StatusPill({ status, label }) {
  const key = String(status);
  const text = label || STATUS_LABELS[key] || key;
  return <span className={`status-pill status-pill--${key.toLowerCase()}`}>{text}</span>;
}

export function AdminPageHead({ eyebrow, title, description, actions }) {
  return (
    <header className="admin-page-head">
      <div>
        {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="admin-page-actions">{actions}</div> : null}
    </header>
  );
}

export function AdminSearch({ value, onChange, placeholder = "Search", className = "" }) {
  return (
    <label className={`search-field search-field--sm admin-search ${className}`}>
      <Search size={15} />
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
      />
    </label>
  );
}

export function AdminEmpty({ title, message, icon, action }) {
  return <EmptyState icon={icon} title={title} message={message} action={action} />;
}

export function AdminTableLoading({ rows = 5, columns = 4 }) {
  return (
    <div className="admin-table-wrap">
      <table className="admin-table">
        <thead>
          <tr>
            {Array.from({ length: columns }).map((_, index) => (
              <th key={index}>
                <Skeleton style={{ width: 70, height: 10 }} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, row) => (
            <tr key={row}>
              {Array.from({ length: columns }).map((_, column) => (
                <td key={column}>
                  <Skeleton style={{ width: column === 0 ? "70%" : "45%", height: 14 }} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = "Confirm",
  danger = true,
  busy = false,
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <>
          <button type="button" className="btn btn--ghost btn--sm" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            type="button"
            className={`btn btn--sm ${danger ? "btn--danger" : "btn--gold"}`}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? <Spinner size={14} label="Working" /> : null} {confirmLabel}
          </button>
        </>
      }
    >
      <p className="modal-copy">{message}</p>
    </Modal>
  );
}

export function MiniStat({ label, value, hint, tone = "" }) {
  return (
    <div className={`mini-stat ${tone ? `mini-stat--${tone}` : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}

export function FieldError({ children }) {
  if (!children) return null;
  return <small className="field-error">{children}</small>;
}
