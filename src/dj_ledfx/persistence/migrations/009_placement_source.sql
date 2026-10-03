-- Light-output fixes: where each placement came from, so a refit never moves the owner's.
-- seed is home.json's, guess is the app's (a spread spot, or a refit to the light's form),
-- and owner is the owner's (placed through the API, or an old scene's placement moved on).
-- A row from before this column is a guess, except the first start's. Those rows were all
-- written in one transaction with the home_placements_seeded mark, so they are the rows
-- within a second of the earliest, once the mark exists. They become seed, or owner where
-- an old scene placed the device

ALTER TABLE placements ADD COLUMN source TEXT NOT NULL DEFAULT 'guess';

UPDATE placements SET source = 'seed'
WHERE EXISTS (SELECT 1 FROM config WHERE section = '_meta' AND key = 'home_placements_seeded')
AND julianday(updated_at) < (SELECT MIN(julianday(updated_at)) FROM placements) + 1.0 / 86400;

UPDATE placements SET source = 'owner'
WHERE source = 'seed' AND target_id IN (SELECT device_id FROM scene_placements)
