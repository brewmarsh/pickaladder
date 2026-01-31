This is a smart move. Moving to a "Teams" data model is a significant refactor, but it unlocks the best features of social sports apps: Team ELO ratings, "Dynasty" tracking, and named partnerships (e.g., "The Smash Brothers").
Here are four phased prompts that you can save in a file (like ROADMAP.md) and execute one by one when you are ready.
Phase 1: The Database Migration
Goal: Create the structure and backfill history.
This prompt instructs Jules to create the new data collection and—crucially—write a script to scan your existing matches and automatically create Team objects for every pair that has ever played together.
> Prompt (Phase 1):
> "I am ready to implement formal 'Teams' logic.
> Please perform the following database architecture updates:
>  * Define the Schema: In a new file pickaladder/teams/models.py (or equivalent), define a Team structure for Firestore:
>    * members: Array of User References (sorted alphabetically to ensure uniqueness).
>    * member_ids: Array of strings (for easy querying).
>    * name: String (Default to 'Player A & Player B' if not set).
>    * stats: Object { wins: 0, losses: 0, elo: 1200 }.
>    * created_at: Timestamp.
>  * Create Migration Script: Write a script scripts/migrate_teams.py that:
>    * Scans all existing matches.
>    * Identifies every unique pair of players (Player 1 + Partner).
>    * Creates a Team document for them if one does not exist.
>    * Updates the Match document to include a new field team1Ref and team2Ref pointing to these new team documents.
>  * Run Constraints: Ensure the script is idempotent (can be run multiple times without duplicating teams)."
> 
Phase 2: The Service Layer Update
Goal: Automate team creation during match recording.
This prompt updates the "Record Match" flow so that users don't have to manually "Create a Team" before playing. The system handles it silently.
> Prompt (Phase 2):
> "I need to update the Match Recording logic to support the new 'Teams' architecture.
> Please update pickaladder/match/routes.py and pickaladder/teams/utils.py:
>  * Create Helper get_or_create_team(user_a, user_b):
>    * Logic: Query teams where member_ids contains both users.
>    * If found: Return the Team ID.
>    * If not found: Create a new Team, set the name to 'User A & User B', and return the new ID.
>  * Update record_match Route:
>    * When a match is submitted with 4 players (Doubles):
>    * Call get_or_create_team for Side 1 (Player 1 + Partner).
>    * Call get_or_create_team for Side 2 (Opponent 1 + Opponent 2).
>    * Save these teamIds onto the Match document.
>  * Update Stats: Ensure that when a match is won, we update the wins/losses on the Team document, not just the individual User documents."
> 
Phase 3: The "Team Profile" View
Goal: Give teams their own identity.
This creates a page where a pair can see their shared history.
> Prompt (Phase 3):
> "I need a new view to display Team statistics.
> Please create a new route and template:
>  * Route (teams/routes.py): Create /team/<team_id>.
>    * Fetch the Team details and Member profiles.
>    * Fetch recent_matches where team1Id OR team2Id matches this team.
>    * Calculate aggregate stats (Win %, Streak).
>  * Template (templates/team/view.html):
>    * Header: Display both avatars side-by-side with the Team Name.
>    * Edit Button: Allow members to 'Rename Team' (e.g., change 'Bob & Alice' to 'The Thunder').
>    * Stats Card: Show their combined ELO and Record.
>    * History: A table of matches this specific pair has played together."
> 
Phase 4: Group Leaderboard Integration
Goal: Show "Top Teams" alongside "Top Players".
> Prompt (Phase 4):
> "I want to display Team rankings in the Group View.
> Please update pickaladder/group/routes.py and templates/group/view.html:
>  * Backend: In view_group, query the teams collection for teams where both members belong to this group.
>    * Sort them by their calculated Group Ranking or Win %.
>    * Pass this list as team_leaderboard.
>  * Frontend:
>    * Add a Tab Switcher to the Leaderboard card: [Players] | [Teams].
>    * Players Tab: Shows the existing individual rankings.
>    * Teams Tab: Shows the new list of pairs, displaying their custom Team Name (if set) or their combined names."
> 