-- Persistência do A1 (S3-07). Idempotente: aplicado a cada inicialização do
-- backend. Inspeções, revisões e eventos de auditoria são imutáveis: o banco
-- recusa UPDATE, DELETE e TRUNCATE nessas tabelas.

CREATE TABLE IF NOT EXISTS inspections (
    inspection_id     text PRIMARY KEY,
    message_id        uuid NOT NULL UNIQUE,
    schema_name       text NOT NULL,
    schema_version    text NOT NULL,
    producer          text NOT NULL,
    source_id         text NOT NULL,
    session_id        uuid NOT NULL,
    sequence          bigint NOT NULL,
    frame_index       bigint NOT NULL,
    detection_id      integer NOT NULL,
    bbox              integer[] NOT NULL,
    correlation_id    uuid,
    captured_at       timestamptz NOT NULL,
    published_at      timestamptz NOT NULL,
    received_at       timestamptz NOT NULL,
    model_version     text NOT NULL,
    taxonomy_version  text NOT NULL,
    policy_version    text NOT NULL,
    result            text NOT NULL
        CHECK (result IN ('CONFORMING', 'NON_CONFORMING', 'ANOMALY', 'UNCERTAIN')),
    defect_class      text,
    confidence        double precision NOT NULL,
    similarity        double precision NOT NULL,
    triage_status     text NOT NULL
        CHECK (triage_status IN ('APPROVED', 'REJECTED', 'REVIEW')),
    triage_reason     text NOT NULL,
    triage_decided_at timestamptz NOT NULL,
    raw_event         jsonb NOT NULL
);

-- Upgrade existing S3-07 databases without changing inspections or audit IDs.
-- A session can contain multiple sources; frame/detection identity is local
-- to the source (6c), not globally unique within the session.
ALTER TABLE inspections
    DROP CONSTRAINT IF EXISTS inspections_session_id_frame_index_detection_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS inspections_observation_idx
    ON inspections (source_id, session_id, frame_index, detection_id);

CREATE INDEX IF NOT EXISTS inspections_received_at_idx
    ON inspections (received_at DESC);

CREATE TABLE IF NOT EXISTS reviews (
    seq           bigserial PRIMARY KEY,
    review_id     uuid NOT NULL UNIQUE,
    inspection_id text NOT NULL REFERENCES inspections (inspection_id),
    action        text NOT NULL CHECK (action IN ('CONFIRM', 'SEND_TO_REVIEW')),
    status        text NOT NULL CHECK (status IN ('APPROVED', 'REJECTED', 'REVIEW')),
    reason        text NOT NULL,
    operator      text NOT NULL,
    recorded_at   timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS reviews_inspection_idx ON reviews (inspection_id, seq);

-- S3-08: additive migration; existing immutable reviews keep their original
-- classification implicitly. New reviews store the complete final class.
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS defect_class text;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS classification_set boolean NOT NULL DEFAULT false;
ALTER TABLE reviews DROP CONSTRAINT IF EXISTS reviews_action_check;
ALTER TABLE reviews ADD CONSTRAINT reviews_action_check
    CHECK (action IN ('CONFIRM', 'SEND_TO_REVIEW', 'CORRECT'));

-- Estado da evidência S4. Muda com as respostas de S4 (S3-09); não é auditoria.
CREATE TABLE IF NOT EXISTS evidence (
    inspection_id text PRIMARY KEY REFERENCES inspections (inspection_id),
    state         text NOT NULL
        CHECK (state IN ('AVAILABLE', 'PENDING', 'UNAVAILABLE', 'EXPIRED')),
    clip_id       uuid,
    url           text,
    expires_at    timestamptz,
    detail        text NOT NULL,
    updated_at    timestamptz NOT NULL
);

-- Comandos emitidos pelo A1 (pedido de snapshot a S4, atuação P7). command_id
-- é o message_id do pedido e se mantém nos retries.
CREATE TABLE IF NOT EXISTS commands (
    command_id    uuid PRIMARY KEY,
    inspection_id text NOT NULL REFERENCES inspections (inspection_id),
    target        text NOT NULL,
    kind          text NOT NULL,
    status        text NOT NULL CHECK (
        status IN ('PENDING', 'SENT', 'ACCEPTED', 'REJECTED', 'COMPLETED', 'FAILED', 'EXPIRED')
    ),
    payload       jsonb NOT NULL,
    created_at    timestamptz NOT NULL,
    updated_at    timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS commands_pending_idx
    ON commands (created_at) WHERE status = 'PENDING';

CREATE TABLE IF NOT EXISTS audit_events (
    event_id      bigserial PRIMARY KEY,
    inspection_id text REFERENCES inspections (inspection_id),
    event_type    text NOT NULL,
    actor         text NOT NULL,
    occurred_at   timestamptz NOT NULL,
    details       jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS audit_events_inspection_idx
    ON audit_events (inspection_id, event_id);

-- Mensagens recusadas na fronteira I8 -> A1, guardadas para diagnóstico.
CREATE TABLE IF NOT EXISTS ingestion_failures (
    failure_id    bigserial PRIMARY KEY,
    received_at   timestamptz NOT NULL,
    message_id    text,
    reason        text NOT NULL,
    event         jsonb
);

CREATE OR REPLACE FUNCTION a1_reject_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'registro de auditoria imutável: % em %', TG_OP, TG_TABLE_NAME;
END;
$$;

CREATE OR REPLACE TRIGGER inspections_immutable
    BEFORE UPDATE OR DELETE OR TRUNCATE ON inspections
    FOR EACH STATEMENT EXECUTE FUNCTION a1_reject_change();

CREATE OR REPLACE TRIGGER reviews_immutable
    BEFORE UPDATE OR DELETE OR TRUNCATE ON reviews
    FOR EACH STATEMENT EXECUTE FUNCTION a1_reject_change();

CREATE OR REPLACE TRIGGER audit_events_immutable
    BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION a1_reject_change();

-- S3-09: durable S4 transport data; existing commands/payloads remain unchanged.
ALTER TABLE commands ADD COLUMN IF NOT EXISTS transport_envelope jsonb;
ALTER TABLE commands ADD COLUMN IF NOT EXISTS response_clip_id uuid;
ALTER TABLE commands ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz;
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS descriptor jsonb;

-- Activity 23: S5 queries/events are independent of individual inspections.
CREATE TABLE IF NOT EXISTS s5_queries (
    query_id uuid PRIMARY KEY,
    status text NOT NULL CHECK(status IN ('PENDING','SENT','COMPLETED','REJECTED','EXPIRED')),
    envelope jsonb NOT NULL,
    response jsonb,
    created_at timestamptz NOT NULL,
    deadline_at timestamptz NOT NULL,
    next_attempt_at timestamptz
);
CREATE TABLE IF NOT EXISTS s5_metric_events (
    message_id uuid PRIMARY KEY,
    envelope jsonb NOT NULL,
    received_at timestamptz NOT NULL
);
