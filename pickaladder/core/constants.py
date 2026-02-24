"""Global constants for the pickaladder application."""

# Database-related constants
DB_NAME = "pickaladder"
FIRESTORE_BATCH_LIMIT = 400

# External Links
# Placeholder - confirm official base URL
DUPR_PROFILE_BASE_URL = "REPLACE_WITH_ACTUAL_DUPR_URL"

# Table names
USERS_TABLE = "users"
FRIENDS_TABLE = "friends"
MATCHES_TABLE = "matches"
MIGRATIONS_TABLE = "migrations"

# Columns for 'users' table
USER_ID = "id"
USER_USERNAME = "username"
USER_PASSWORD = "password"  # nosec B105
USER_EMAIL = "email"
USER_NAME = "name"
USER_DUPR_RATING = "dupr_rating"
USER_IS_ADMIN = "is_admin"
USER_PROFILE_PICTURE = "profile_picture"
USER_PROFILE_PICTURE_THUMBNAIL = "profile_picture_thumbnail"
USER_DARK_MODE = "dark_mode"
USER_EMAIL_VERIFIED = "email_verified"
USER_RESET_TOKEN = "reset_token"  # nosec B105
USER_RESET_TOKEN_EXPIRATION = "reset_token_expiration"  # nosec B105

# Columns for 'friends' table
FRIENDS_USER_ID = "user_id"
FRIENDS_FRIEND_ID = "friend_id"
FRIENDS_STATUS = "status"

# Columns for 'matches' table
MATCH_ID = "id"
MATCH_PLAYER1_ID = "player1_id"
MATCH_PLAYER2_ID = "player2_id"
MATCH_PLAYER1_SCORE = "player1_score"
MATCH_PLAYER2_SCORE = "player2_score"
MATCH_DATE = "match_date"

# Columns for 'migrations' table
MIGRATION_ID = "id"
MIGRATION_NAME = "migration_name"

# Group-related constants
RECENT_MATCHES_LIMIT = 5
HOT_STREAK_THRESHOLD = 3

# Leaderboard-related constants
GLOBAL_LEADERBOARD_MIN_GAMES = 1

# Email-related constants
SMTP_AUTH_ERROR_CODE = 534

JOKES = [
    "Why did the pickleball player get arrested? Because he was caught smashing!",
    "What do you call a girl standing in the middle of a tennis court? Annette.",
    "Why are fish never good at tennis? Because they don't like getting close to the net.",
    "What is a tennis player's favorite city? Volley-wood.",
    "Why do tennis players never get married? Because love means nothing to them.",
    "What time does a tennis player go to bed? Ten-ish.",
    "Why did the pickleball hit the net? It wanted to see what was on the other side.",
    "How is a pickleball game like a waiter? They both serve.",
    "Why should you never fall in love with a tennis player? To them, 'Love' means nothing.",
    "What do you serve but not eat? A tennis ball.",
]
