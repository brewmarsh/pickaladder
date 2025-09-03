ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_picture_path VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_picture_thumbnail_path VARCHAR(255);
