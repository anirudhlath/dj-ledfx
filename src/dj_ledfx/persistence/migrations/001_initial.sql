-- Initial schema for dj-ledfx state database

CREATE TABLE IF NOT EXISTS config (
    section TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (section, key)
);

CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    backend TEXT NOT NULL,
    led_count INTEGER,
    ip TEXT,
    mac TEXT,
    device_id TEXT,
    sku TEXT,
    last_latency_ms REAL,
    last_seen TEXT,
    extra TEXT
);

CREATE TABLE IF NOT EXISTS groups (
    name TEXT PRIMARY KEY,
    color TEXT NOT NULL DEFAULT '#888888'
);

CREATE TABLE IF NOT EXISTS device_groups (
    group_name TEXT NOT NULL REFERENCES groups(name) ON DELETE CASCADE,
    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    PRIMARY KEY (group_name, device_id)
);

CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mapping_type TEXT NOT NULL DEFAULT 'linear',
    mapping_params TEXT,
    effect_mode TEXT NOT NULL DEFAULT 'independent',
    effect_source TEXT REFERENCES scenes(id) ON DELETE SET NULL,
    is_active INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scene_effect_state (
    scene_id TEXT PRIMARY KEY REFERENCES scenes(id) ON DELETE CASCADE,
    effect_class TEXT NOT NULL,
    params TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scene_placements (
    scene_id TEXT NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    position_x REAL NOT NULL DEFAULT 0,
    position_y REAL NOT NULL DEFAULT 0,
    position_z REAL NOT NULL DEFAULT 0,
    geometry_type TEXT NOT NULL DEFAULT 'point',
    direction_x REAL,
    direction_y REAL,
    direction_z REAL,
    length REAL,
    width REAL,
    rows INTEGER,
    cols INTEGER,
    PRIMARY KEY (scene_id, device_id)
);

CREATE TABLE IF NOT EXISTS presets (
    name TEXT PRIMARY KEY,
    effect_class TEXT NOT NULL,
    params TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scenes_active ON scenes(is_active);
CREATE INDEX IF NOT EXISTS idx_placements_device ON scene_placements(device_id);
