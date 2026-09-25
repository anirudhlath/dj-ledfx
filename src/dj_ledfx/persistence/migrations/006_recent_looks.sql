-- M2: the looks that stopped, for the web app's "Start again" (ruling 19)

-- One row per zone and look, holding its newest stop. No foreign keys, so remembering a
-- stop never fails: an entry whose look is gone is left out when the list is read, and a
-- deleted zone's entries are deleted with it (ZoneStore)
CREATE TABLE IF NOT EXISTS recent_looks (
    zone_id TEXT NOT NULL,
    look_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    stopped_at TEXT NOT NULL,
    PRIMARY KEY (zone_id, look_id)
)
