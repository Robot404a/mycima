import { useMemo } from "react";
import { computeSeatGeometry, seatColor } from "../lib/seats";
import { money } from "../lib/format";

const UNIT_X = 19;
const UNIT_Y = 22;
const MARGIN_X = 46;
const MARGIN_TOP = 78;

export function SeatPlan2D({ seats, layout, selectedIds, onToggle }) {
  const selected = selectedIds instanceof Set ? selectedIds : new Set(selectedIds || []);
  const geometry = useMemo(() => computeSeatGeometry(seats, layout), [seats, layout]);
  const width = geometry.width * 1.02 * UNIT_X + MARGIN_X * 2;
  const height = geometry.rowCount * UNIT_Y + MARGIN_TOP + 60;
  const screenWidth = width - MARGIN_X * 2.8;

  return (
    <div className="seat-plan-scroll">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="seat-plan"
        role="group"
        aria-label="Interactive cinema seat plan"
        style={{ minWidth: Math.min(820, Math.max(520, width * 0.7)) }}
      >
        <defs>
          <linearGradient id="screen-glow" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f5eddc" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#c9a45c" stopOpacity="0.12" />
          </linearGradient>
          <radialGradient id="plan-glow" cx="50%" cy="0%" r="70%">
            <stop offset="0%" stopColor="#c9a45c" stopOpacity="0.16" />
            <stop offset="100%" stopColor="#c9a45c" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width={width} height={height} fill="url(#plan-glow)" />
        <path
          d={`M ${MARGIN_X + 24} 34 Q ${width / 2} 52 ${width - MARGIN_X - 24} 34`}
          fill="none"
          stroke="url(#screen-glow)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        <text x={width / 2} y={20} textAnchor="middle" className="seat-plan-screen-label">
          SCREEN
        </text>
        {seats.map((seat) => {
          const position = geometry.geometry.get(seat.seat_id);
          if (!position) return null;
          const isSelected = selected.has(seat.seat_id);
          const x = MARGIN_X + (position.x + (geometry.width * 1.02) / 2) * UNIT_X;
          const y = MARGIN_TOP + (Number(seat.y) || 0) * UNIT_Y;
          const label = `Seat ${seat.seat_id}, ${seat.category}, ${seat.price ? money(seat.price) : ""}, ${seat.status.toLowerCase()}${isSelected ? ", selected" : ""}`;
          return (
            <g
              key={seat.seat_id}
              className={`plan-seat plan-seat--${seat.status.toLowerCase()} ${isSelected ? "is-selected" : ""}`}
              role="button"
              tabIndex={0}
              aria-label={label}
              aria-pressed={isSelected}
              onClick={() => onToggle?.(seat)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onToggle?.(seat);
                }
              }}
            >
              <title>{label}</title>
              <rect
                x={x - 6.4}
                y={y}
                width={12.8}
                height={11}
                rx={2.6}
                fill={seatColor(seat, isSelected)}
                stroke={isSelected ? "#f4e4bb" : seat.held_by_me ? "#e8cb8e" : "transparent"}
                strokeWidth={isSelected || seat.held_by_me ? 1.4 : 0}
              />
              {seat.category !== "REGULAR" ? (
                <>
                  <rect
                    x={x - 5}
                    y={y + 9}
                    width={10}
                    height={2}
                    rx={1}
                    fill={seat.category === "VVIP" ? "#f2d99d" : "#d8c49b"}
                    opacity="0.95"
                  />
                  <rect
                    x={x - 2.5}
                    y={y + 11.2}
                    width={5}
                    height={1.5}
                    rx={0.75}
                    fill={seat.category === "VVIP" ? "#f2d99d" : "#d8c49b"}
                    opacity="0.9"
                  />
                </>
              ) : null}
            </g>
          );
        })}
        {Array.from({ length: geometry.rowCount }).map((_, row) => (
          <g key={`row-${row}`}>
            <text
              x={MARGIN_X - 16}
              y={MARGIN_TOP + row * UNIT_Y + 9}
              textAnchor="middle"
              className="seat-plan-row-label"
            >
              {String.fromCharCode(65 + row)}
            </text>
            <text
              x={width - MARGIN_X + 16}
              y={MARGIN_TOP + row * UNIT_Y + 9}
              textAnchor="middle"
              className="seat-plan-row-label"
            >
              {String.fromCharCode(65 + row)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
