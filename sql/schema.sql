CREATE TABLE IF NOT EXISTS stores (
    store_id text PRIMARY KEY,
    department_store text NOT NULL,
    branch text NOT NULL,
    city text NOT NULL,
    brand text NOT NULL,
    latitude double precision,
    longitude double precision,
    allowed_radius_meter integer,
    status text NOT NULL,
    notes text
);

CREATE TABLE IF NOT EXISTS users (
    user_id text PRIMARY KEY,
    role text NOT NULL,
    name text NOT NULL,
    phone text,
    email text,
    pin text NOT NULL,
    telegram_user_id bigint,
    telegram_chat_id bigint,
    status text NOT NULL,
    notes text
);

CREATE TABLE IF NOT EXISTS daily_reports (
    report_id text PRIMARY KEY,
    report_date date NOT NULL,
    store_id text NOT NULL REFERENCES stores(store_id),
    user_id text NOT NULL REFERENCES users(user_id),
    traffic integer NOT NULL,
    offline_gmv numeric NOT NULL,
    online_gmv numeric NOT NULL,
    order_count integer NOT NULL,
    pieces_sold integer NOT NULL,
    no_buy_reason text NOT NULL,
    stock_issue text NOT NULL,
    submitted_latitude double precision,
    submitted_longitude double precision,
    distance_from_store_meter numeric,
    note text NOT NULL,
    submission_status text NOT NULL CHECK (submission_status IN ('submitted', 'correction')),
    location_status text NOT NULL CHECK (location_status IN ('in_radius', 'out_of_radius', 'manual_store_selection')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bot_sessions (
    telegram_chat_id bigint PRIMARY KEY,
    telegram_user_id bigint,
    current_step text NOT NULL,
    selected_store_id text,
    user_id text,
    draft_report jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL
);

DO $$
BEGIN
    IF to_regclass('public.ui_translate') IS NULL
       AND to_regclass('public.message_templates') IS NOT NULL THEN
        ALTER TABLE message_templates RENAME TO ui_translate;
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS ui_translate (
    key text PRIMARY KEY,
    category text NOT NULL DEFAULT 'general',
    message text NOT NULL,
    description text NOT NULL DEFAULT '',
    updated_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF to_regclass('public.message_templates') IS NOT NULL THEN
        INSERT INTO ui_translate (key, category, message, description, updated_at)
        SELECT key, category, message, description, updated_at
        FROM message_templates
        ON CONFLICT (key) DO UPDATE
        SET category = EXCLUDED.category,
            message = EXCLUDED.message,
            description = EXCLUDED.description,
            updated_at = EXCLUDED.updated_at;

        DROP TABLE message_templates;
    END IF;
END;
$$;

ALTER TABLE ui_translate
    ADD COLUMN IF NOT EXISTS category text NOT NULL DEFAULT 'general',
    ADD COLUMN IF NOT EXISTS description text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DROP INDEX IF EXISTS idx_message_templates_category_key;
CREATE INDEX IF NOT EXISTS idx_ui_translate_category_key
    ON ui_translate(category, key);

CREATE OR REPLACE FUNCTION set_ui_translate_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_message_templates_updated_at ON ui_translate;
DROP TRIGGER IF EXISTS trg_ui_translate_updated_at ON ui_translate;
CREATE TRIGGER trg_ui_translate_updated_at
    BEFORE UPDATE ON ui_translate
    FOR EACH ROW
    EXECUTE FUNCTION set_ui_translate_updated_at();

DROP FUNCTION IF EXISTS set_message_templates_updated_at();

CREATE INDEX IF NOT EXISTS idx_daily_reports_store_date
    ON daily_reports(store_id, report_date);

CREATE INDEX IF NOT EXISTS idx_daily_reports_report_date
    ON daily_reports(report_date);
