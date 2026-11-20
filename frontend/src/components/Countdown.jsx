import { useEffect, useRef } from "react";
import { TimerReset, TimerOff } from "lucide-react";
import { useCountdown } from "../lib/hooks";
import { formatCountdown } from "../lib/format";

export function Countdown({ expiresAt, onExpire, compact = false, label = "Hold expires in" }) {
  const { seconds, expired, active } = useCountdown(expiresAt);
  const fired = useRef(false);

  useEffect(() => {
    fired.current = false;
  }, [expiresAt]);

  useEffect(() => {
    if (expired && !fired.current) {
      fired.current = true;
      onExpire?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expired]);

  if (!expiresAt) return null;
  return (
    <span className={`countdown ${expired ? "is-expired" : ""} ${compact ? "is-compact" : ""}`}>
      {expired ? <TimerOff size={compact ? 14 : 17} /> : <TimerReset size={compact ? 14 : 17} />}
      <span>
        {expired ? "Hold expired" : label}
        {!expired && active ? <strong>{formatCountdown(seconds)}</strong> : null}
      </span>
    </span>
  );
}
