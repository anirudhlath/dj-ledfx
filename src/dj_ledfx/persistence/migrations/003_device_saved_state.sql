CREATE TABLE IF NOT EXISTS device_saved_state (
    stable_id TEXT PRIMARY KEY,
    state_bytes BLOB NOT NULL,
    captured_at TEXT NOT NULL
);
