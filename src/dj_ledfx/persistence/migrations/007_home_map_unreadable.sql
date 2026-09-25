-- M2: a stored home map that can't be read is copied here before anything replaces it,
-- so the owner's work survives the first edit made on the seed map that stands in for it

CREATE TABLE IF NOT EXISTS home_map_unreadable (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    body TEXT NOT NULL,
    set_aside_at TEXT NOT NULL
)
