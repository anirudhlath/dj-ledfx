-- Add device_type column to devices table for fast reconnect
ALTER TABLE devices ADD COLUMN device_type TEXT;
