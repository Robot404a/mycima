-- Reservation service schema (PostgreSQL 13+). Idempotent: the service applies it at startup.
-- IDs from other services (user_id, showtime_id) are plain values, NOT foreign keys:
-- each microservice owns its own database.

-- A hold = a temporary lock on seats while the user pays (expires automatically).
CREATE TABLE IF NOT EXISTS holds (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      BIGINT       NOT NULL,
    showtime_id  BIGINT       NOT NULL,
    status       VARCHAR(12)  NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active', 'converted', 'released', 'expired')),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ  NOT NULL,
    CHECK (expires_at > created_at)
);
CREATE INDEX IF NOT EXISTS idx_holds_user    ON holds (user_id);
CREATE INDEX IF NOT EXISTS idx_holds_expiry  ON holds (expires_at) WHERE status = 'active';

-- A booking = a confirmed (paid) reservation.
CREATE TABLE IF NOT EXISTS bookings (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       BIGINT        NOT NULL,
    showtime_id   BIGINT        NOT NULL,
    hold_id       UUID          UNIQUE REFERENCES holds (id),
    status        VARCHAR(12)   NOT NULL DEFAULT 'confirmed'
                  CHECK (status IN ('confirmed', 'cancelled')),
    total_amount  NUMERIC(10,2) NOT NULL CHECK (total_amount >= 0),
    payment_ref   VARCHAR(100),
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    cancelled_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_bookings_user     ON bookings (user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_showtime ON bookings (showtime_id);

-- One row per seat per showtime that is held or booked.
-- A seat is identified by its label (e.g. 'A5'); the hall layout lives in the Movie service.
CREATE TABLE IF NOT EXISTS seat_claims (
    id           BIGSERIAL PRIMARY KEY,
    showtime_id  BIGINT       NOT NULL,
    seat_label   VARCHAR(10)  NOT NULL,
    status       VARCHAR(10)  NOT NULL DEFAULT 'held'
                 CHECK (status IN ('held', 'booked', 'released')),
    hold_id      UUID         NOT NULL REFERENCES holds (id),
    booking_id   UUID         REFERENCES bookings (id),
    price        NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CHECK (status <> 'booked' OR booking_id IS NOT NULL)
);

-- THE anti-double-booking rule: a seat can have at most one live claim per showtime.
CREATE UNIQUE INDEX IF NOT EXISTS uq_seat_active
    ON seat_claims (showtime_id, seat_label)
    WHERE status IN ('held', 'booked');

CREATE INDEX IF NOT EXISTS idx_claims_hold    ON seat_claims (hold_id);
CREATE INDEX IF NOT EXISTS idx_claims_booking ON seat_claims (booking_id);
