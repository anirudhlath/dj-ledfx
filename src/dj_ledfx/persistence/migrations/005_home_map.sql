-- M2: the home map, and where each light or PC part sits on it

CREATE TABLE IF NOT EXISTS home_map (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    body TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- target_id is a light's id, or a PC part's device id. A light removed while offline
-- keeps its row, so no foreign key.
CREATE TABLE IF NOT EXISTS placements (
    target_id TEXT PRIMARY KEY,
    shape TEXT NOT NULL,
    led_order TEXT NOT NULL DEFAULT '',
    confirmed INTEGER NOT NULL DEFAULT 0,
    confirmed_at TEXT,
    updated_at TEXT NOT NULL
)
