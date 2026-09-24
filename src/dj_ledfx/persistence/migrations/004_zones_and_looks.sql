-- M1: zones, saved looks and what each zone runs

CREATE TABLE IF NOT EXISTS zones (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'group',
    all_lights INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS zone_members (
    zone_id TEXT NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (zone_id, device_id)
);

CREATE TABLE IF NOT EXISTS looks (
    id TEXT PRIMARY KEY,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS look_stars (
    look_id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS zone_assignments (
    zone_id TEXT PRIMARY KEY REFERENCES zones(id) ON DELETE CASCADE,
    look_id TEXT NOT NULL,
    look TEXT NOT NULL,
    brightness REAL NOT NULL DEFAULT 1.0,
    lights TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL
);

-- Captures taken by the old transport. Nothing runs after this migration, so none would be released.
DELETE FROM device_saved_state;

-- M1 removes this setting: lights in no running zone are never changed.
DELETE FROM config WHERE section = 'engine' AND key = 'unassigned_device_mode'
