"""Data models for the teams feature."""

# Team data model is now primarily managed via TeamRepository.
# Standard team documents contain:
# - member_ids: list[str] (sorted)
# - members: list[DocumentReference]
# - name: str
# - stats: dict (wins, losses, elo)
# - createdAt: timestamp
