-- Create the friend_groups table
CREATE TABLE friend_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    owner_id UUID REFERENCES users(id) ON DELETE CASCADE
);

-- Create the friend_group_members table
CREATE TABLE friend_group_members (
    group_id UUID REFERENCES friend_groups(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, user_id)
);
