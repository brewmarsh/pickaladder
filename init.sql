DROP TABLE IF EXISTS friends, matches, users CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT,
    name TEXT,
    dupr_rating NUMERIC(3, 2),
    is_admin BOOLEAN DEFAULT FALSE,
    profile_picture TEXT,
    dark_mode BOOLEAN DEFAULT FALSE
);

CREATE TABLE friends (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    friend_id UUID REFERENCES users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    PRIMARY KEY (user_id, friend_id)
);

CREATE TABLE matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player1_id UUID REFERENCES users(id),
    player2_id UUID REFERENCES users(id),
    player1_score INTEGER,
    player2_score INTEGER,
    match_date DATE
);
