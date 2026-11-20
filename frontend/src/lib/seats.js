/**
 * Shared geometry for the 3D hall and the accessible 2D plan.
 * Aisles are visual gaps after the given seat numbers (1-based).
 */
export function computeSeatGeometry(seats = [], layout = {}) {
  const maxX = Math.max(
    Number(layout.max_x) || 0,
    ...seats.map((seat) => Number(seat.x) || 0),
    1,
  );
  const rowCount = Math.max(
    Number(layout.row_count) || 0,
    ...seats.map((seat) => (Number(seat.y) || 0) + 1),
    1,
  );
  const aisles = new Set((layout.aisles_after || []).map(Number));
  const gap = 0.62;
  const positions = {};
  let extra = 0;
  for (let n = 1; n <= maxX; n += 1) {
    positions[n] = n + extra;
    if (aisles.has(n)) extra += gap;
  }
  const width = maxX + extra;
  const center = (1 + width) / 2;
  const seatGapZ = 0.96;
  const geometry = new Map();
  let minZ = Infinity;
  let maxZ = -Infinity;
  for (const seat of seats) {
    const x = ((positions[Number(seat.x)] || Number(seat.x)) - center) * 1.02;
    const z = ((Number(seat.y) || 0) - (rowCount - 1) / 2) * seatGapZ;
    minZ = Math.min(minZ, z);
    maxZ = Math.max(maxZ, z);
    geometry.set(seat.seat_id, { x, z });
  }
  return {
    geometry,
    width,
    rowCount,
    maxX,
    aisles,
    center,
    minZ: Number.isFinite(minZ) ? minZ : 0,
    maxZ: Number.isFinite(maxZ) ? maxZ : 0,
    floorWidth: width * 1.02 + 2.6,
    floorDepth: rowCount * seatGapZ + 4.2,
  };
}

export const SEAT_COLORS = {
  AVAILABLE: "#5faf93",
  HELD: "#cf8d4f",
  BOOKED: "#8a9099",
  SELECTED: "#6f8ff2",
  MINE: "#c9a45c",
  VIP: "#c9a45c",
  VVIP: "#efd9a0",
};

export function seatColor(seat, selected) {
  if (selected) return SEAT_COLORS.SELECTED;
  if (seat.status === "AVAILABLE") {
    if (seat.category === "VVIP") return SEAT_COLORS.VVIP;
    if (seat.category === "VIP") return SEAT_COLORS.VIP;
    return SEAT_COLORS.AVAILABLE;
  }
  if (seat.status === "HELD") return seat.held_by_me ? SEAT_COLORS.MINE : SEAT_COLORS.HELD;
  if (seat.status === "BOOKED") return SEAT_COLORS.BOOKED;
  return "#444";
}
