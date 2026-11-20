import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { useLockBody } from "../lib/hooks";

export function Modal({ open, onClose, title, subtitle, children, footer, size = "md" }) {
  const ref = useRef(null);
  useLockBody(open);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    document.addEventListener("keydown", onKey);
    const timer = setTimeout(() => {
      const target = ref.current?.querySelector(
        "input:not([type=hidden]), textarea, select, button",
      );
      target?.focus();
    }, 60);
    return () => {
      document.removeEventListener("keydown", onKey);
      clearTimeout(timer);
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose?.();
      }}
    >
      <div className={`modal modal--${size}`} role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <header className="modal-head">
          <div>
            <h2>{title}</h2>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close dialog">
            <X size={18} />
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer ? <footer className="modal-foot">{footer}</footer> : null}
      </div>
    </div>
  );
}
