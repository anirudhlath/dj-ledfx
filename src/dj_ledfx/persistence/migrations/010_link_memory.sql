-- Light sync: each light's link memory, the latency and mode it last had, so the first look
-- after a restart starts every light where it was (light-sync spec §7). latency_ms is the
-- latency strategy's, before the display delay and the offset. dozing is 1 while the doze
-- check calls the light's Wi-Fi dozing. A cache, measured again within seconds of a start,
-- so backups leave it out

CREATE TABLE IF NOT EXISTS link_memory (
    stable_id TEXT PRIMARY KEY,
    latency_ms REAL NOT NULL,
    dozing INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
