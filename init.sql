CREATE TABLE users (
    id SERIAL PRIMARY KEY,
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
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    friend_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    PRIMARY KEY (user_id, friend_id)
);

CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    player1_id INTEGER REFERENCES users(id),
    player2_id INTEGER REFERENCES users(id),
    player1_score INTEGER,
    player2_score INTEGER,
    match_date DATE
);
