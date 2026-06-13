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
    submitted_latitude double precision NOT NULL,
    submitted_longitude double precision NOT NULL,
    distance_from_store_meter numeric NOT NULL,
    note text NOT NULL,
    submission_status text NOT NULL CHECK (submission_status IN ('submitted', 'correction')),
    location_status text NOT NULL CHECK (location_status IN ('in_radius', 'out_of_radius')),
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

CREATE TABLE IF NOT EXISTS message_templates (
    key text PRIMARY KEY,
    message text NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_daily_reports_store_date
    ON daily_reports(store_id, report_date);

CREATE INDEX IF NOT EXISTS idx_daily_reports_report_date
    ON daily_reports(report_date);
