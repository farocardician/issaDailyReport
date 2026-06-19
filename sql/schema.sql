CREATE TABLE IF NOT EXISTS stores (
    store_id text PRIMARY KEY,
    outlet text NOT NULL,
    branch text NOT NULL,
    city text NOT NULL,
    brand text NOT NULL,
    latitude double precision,
    longitude double precision,
    allowed_radius_meter integer,
    status text NOT NULL,
    notes text
);

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='stores' AND column_name='department_store')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='stores' AND column_name='outlet') THEN
    ALTER TABLE stores RENAME COLUMN department_store TO outlet;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS users (
    user_id text PRIMARY KEY,
    role text NOT NULL,
    name text NOT NULL,
    phone text,
    email text,
    telegram_user_id bigint,
    telegram_chat_id bigint,
    status text NOT NULL,
    notes text
);

ALTER TABLE users
    DROP COLUMN IF EXISTS pin;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_telegram_user_id
    ON users(telegram_user_id)
    WHERE telegram_user_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS gmv_sources (
    gmv_source_id text PRIMARY KEY,
    label text NOT NULL,
    source_type text NOT NULL DEFAULT 'other',
    requires_traffic boolean NOT NULL DEFAULT false,
    sort_order integer NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'Aktif'
);

CREATE INDEX IF NOT EXISTS idx_gmv_sources_active_order
    ON gmv_sources(status, sort_order);

CREATE TABLE IF NOT EXISTS brands (
    brand_id text PRIMARY KEY,
    label text NOT NULL,
    short_code text NOT NULL DEFAULT '',
    sort_order integer NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'Aktif'
);

CREATE INDEX IF NOT EXISTS idx_brands_active_order
    ON brands(status, sort_order);

CREATE TABLE IF NOT EXISTS outlet (
    outlet_id text PRIMARY KEY,
    label text NOT NULL,
    short_code text NOT NULL DEFAULT '',
    sort_order integer NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'Aktif'
);

CREATE INDEX IF NOT EXISTS idx_outlet_active_order
    ON outlet(status, sort_order);

CREATE TABLE IF NOT EXISTS stock_issues (
    stock_issue_id text PRIMARY KEY,
    label text NOT NULL,
    sort_order integer NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'Aktif'
);

CREATE INDEX IF NOT EXISTS idx_stock_issues_active_order
    ON stock_issues(status, sort_order);

CREATE TABLE IF NOT EXISTS daily_reports (
    report_id text PRIMARY KEY,
    report_date date NOT NULL,
    store_id text NOT NULL REFERENCES stores(store_id),
    user_id text NOT NULL REFERENCES users(user_id),
    stock_issue text NOT NULL,
    submitted_latitude double precision,
    submitted_longitude double precision,
    distance_from_store_meter numeric,
    note text NOT NULL,
    submission_status text NOT NULL CHECK (submission_status IN ('submitted', 'correction')),
    location_status text NOT NULL CHECK (location_status IN ('in_radius', 'out_of_radius', 'manual_store_selection')),
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE daily_reports
    DROP COLUMN IF EXISTS traffic,
    DROP COLUMN IF EXISTS offline_gmv,
    DROP COLUMN IF EXISTS online_gmv,
    DROP COLUMN IF EXISTS order_count,
    DROP COLUMN IF EXISTS pieces_sold,
    DROP COLUMN IF EXISTS no_buy_reason;

CREATE TABLE IF NOT EXISTS daily_report_sales (
    report_id text NOT NULL REFERENCES daily_reports(report_id) ON DELETE CASCADE,
    gmv_source_id text NOT NULL REFERENCES gmv_sources(gmv_source_id),
    source_label text NOT NULL,
    source_type text,
    requires_traffic boolean NOT NULL DEFAULT false,
    traffic integer,
    gmv numeric NOT NULL,
    order_count integer NOT NULL,
    pieces_sold integer NOT NULL,
    sort_order integer NOT NULL DEFAULT 0,
    PRIMARY KEY (report_id, gmv_source_id)
);

CREATE INDEX IF NOT EXISTS idx_daily_report_sales_report
    ON daily_report_sales(report_id);

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
