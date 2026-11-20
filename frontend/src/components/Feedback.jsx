import { useEffect, useState } from "react";
import { Film, LoaderCircle } from "lucide-react";

export function Poster({ src, title, className = "", loading = "lazy" }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [src]);
  if (!src || failed) {
    return (
      <div className={`poster-fallback ${className}`} role="img" aria-label={title}>
        <Film size={26} />
        <span>{title}</span>
      </div>
    );
  }
  return (
    <img
      className={`poster-image ${className}`}
      src={src}
      alt={title ? `${title} poster` : ""}
      loading={loading}
      onError={() => setFailed(true)}
    />
  );
}

export function Spinner({ size = 22, label = "Loading" }) {
  return (
    <span className="spinner" role="status" aria-label={label}>
      <LoaderCircle size={size} />
    </span>
  );
}

export function Skeleton({ className = "", style }) {
  return <div className={`skeleton ${className}`} style={style} aria-hidden="true" />;
}

export function PageLoader({ label = "Preparing the room" }) {
  return (
    <div className="page-loader">
      <div className="reel-loader" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <p>{label}</p>
    </div>
  );
}

export function EmptyState({ icon: Icon = Film, title, message, action = null }) {
  return (
    <div className="state-card state-card--empty">
      <span className="state-icon">
        <Icon size={24} />
      </span>
      <h3>{title}</h3>
      {message ? <p>{message}</p> : null}
      {action}
    </div>
  );
}

export function ErrorState({ title = "Something went wrong", error, onRetry }) {
  return (
    <div className="state-card state-card--error">
      <span className="state-icon">
        <Film size={24} />
      </span>
      <h3>{title}</h3>
      <p>{error?.message || "Please try again in a moment."}</p>
      {onRetry ? (
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => onRetry()}>
          Try again
        </button>
      ) : null}
    </div>
  );
}
