-- M3: whether config.toml and presets.toml were migrated is a run-once mark
-- (toml_io.TOML_MIGRATED_KEY), no longer "the config table has no rows". A database that
-- already holds the app's config was migrated by that old rule, so it gets the mark and
-- isn't migrated again. The tempo clock's settings (section tempo) were never the app's
-- config, so they don't count

INSERT OR IGNORE INTO config (section, key, value)
SELECT '_meta', 'toml_migrated', '1'
WHERE EXISTS (SELECT 1 FROM config WHERE section NOT IN ('_meta', 'tempo'))
