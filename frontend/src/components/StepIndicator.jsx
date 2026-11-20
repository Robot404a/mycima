import { useEffect, useRef } from "react";
import { Check } from "lucide-react";

export function StepIndicator({ steps, current = 0 }) {
  return (
    <ol className="steps" aria-label="Booking progress">
      {steps.map((step, index) => {
        const complete = index < current;
        const active = index === current;
        return (
          <li key={step} className={`step ${complete ? "is-complete" : ""} ${active ? "is-active" : ""}`}>
            <span className="step-dot">{complete ? <Check size={13} /> : index + 1}</span>
            <span className="step-label">{step}</span>
          </li>
        );
      })}
    </ol>
  );
}
