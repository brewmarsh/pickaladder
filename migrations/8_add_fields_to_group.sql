ALTER TABLE groups ADD COLUMN description TEXT;
ALTER TABLE groups ADD COLUMN is_public BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE groups ADD COLUMN profile_picture_path VARCHAR(255);
ALTER TABLE groups ADD COLUMN profile_picture_thumbnail_path VARCHAR(255);
