CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(50) PRIMARY KEY,
    value VARCHAR(255) NOT NULL
);

INSERT INTO settings (key, value) VALUES ('enforce_email_verification', 'false') ON CONFLICT (key) DO NOTHING;
