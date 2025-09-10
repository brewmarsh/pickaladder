-- Create the groups table
CREATE TABLE groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    owner_id UUID REFERENCES users(id) ON DELETE CASCADE,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE NOT NULL,
    profile_picture_path VARCHAR(255),
    profile_picture_thumbnail_path VARCHAR(255)
);

-- Create the group_members table
CREATE TABLE group_members (
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, user_id)
);
