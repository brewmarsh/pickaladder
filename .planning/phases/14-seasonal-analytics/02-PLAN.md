# Plan: 14-02: Visual Trends & Interactive Charts

**Goal:** Provide visual performance tracking (charts) on user profiles to show progression over time.

## Tasks
1. [ ] Integrate Chart.js via CDN in `layout.html`.
2. [ ] Create a "Performance Trends" card in `user/profile.html`.
    - Visualization: Line chart showing `Point Differential` across completed seasons.
    - Visualization: Bar chart showing `Wins vs Losses` per season.
3. [ ] Implement `InsightsService`:
    - `get_user_achievements(user_id)`: Calculate "Best Rank", "Highest PD Season", "Most Improved".
4. [ ] Display "Achievement Badges" on the profile.

## Technical Details
- **Frontend:** Use vanilla JS to initialize Chart.js with data passed from the backend `season_history`.
- **Optimization:** Data is already available in the `season_history` list; no additional API calls needed for basic charts.

## Success Criteria
- [ ] Users can see a line graph of their performance trend.
- [ ] Profile displays at least one high-level insight (e.g., "Career High Rank: #1").
