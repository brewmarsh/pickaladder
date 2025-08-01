# Database-related constants
DB_NAME = "pickaladder"

# Table names
USERS_TABLE = "users"
FRIENDS_TABLE = "friends"
MATCHES_TABLE = "matches"
MIGRATIONS_TABLE = "migrations"

# Columns for 'users' table
USER_ID = "id"
USER_USERNAME = "username"
USER_PASSWORD = "password"
USER_EMAIL = "email"
USER_NAME = "name"
USER_DUPR_RATING = "dupr_rating"
USER_IS_ADMIN = "is_admin"
USER_PROFILE_PICTURE = "profile_picture"
USER_PROFILE_PICTURE_THUMBNAIL = "profile_picture_thumbnail"
USER_DARK_MODE = "dark_mode"
USER_EMAIL_VERIFIED = "email_verified"

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
