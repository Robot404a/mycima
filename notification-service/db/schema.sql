CREATE TABLE IF NOT EXISTS notifications (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT      NOT NULL,
    recipient_email  TEXT        NOT NULL,
    type             TEXT        NOT NULL
                     CHECK (type IN ('reservation_created', 'reservation_cancelled')),
    reference_id     TEXT,                      -- e.g. the booking id
    subject          TEXT        NOT NULL,
    body             TEXT        NOT NULL,
    status           TEXT        NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'sent', 'failed')),
    attempts         INTEGER     NOT NULL DEFAULT 0,
    last_attempt_at  TIMESTAMPTZ,
    error            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_notifications_user   ON notifications (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications (status)
    WHERE status <> 'sent';

-- One email per (event type, booking): a repeated call from reservation-service is a no-op.
CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_type_ref
    ON notifications (type, reference_id) WHERE reference_id IS NOT NULL;