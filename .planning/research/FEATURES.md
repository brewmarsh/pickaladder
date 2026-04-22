# Feature Landscape

**Domain:** Sports/Pickleball Ladder App
**Researched:** 2026-04-21

## Table Stakes

Features users expect in any ladder/ranking app.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Individual Leaderboard | Track ranking (ELO/DUPR). | Med | Needs reliable match history. |
| Match Recording | Log wins/losses. | Low | Core loop of the app. |
| Group Management | Group friends/clubs. | Med | Privacy and admin controls needed. |
| Team Dashboards | See how a specific pair performs. | Low | Already exists but needs cleanup. |

## Differentiators

Features that set `pickaladder` apart.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Dynamic Team Rosters | Let a "Team" have many members. | High | Requires new junction collection. |
| Hybrid Pair Tracking | Track "The Smashers" but also the specific duo stats inside it. | High | Complex aggregation. |
| Giant Slayer Upsets | Highlight when low-rated players beat high-rated ones. | Low | Already partially implemented. |
| Auto-Friending | frictionless social growth. | Low | Already exists. |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Real-time chat | High maintenance, SEO spam risk. | Use deep links to WhatsApp/Discord. |
| Financial Transactions | Compliance/Security burden. | Keep purely social/competitive. |

## Feature Dependencies

```
Group Membership → Match Recording
Match Recording → Team Entity (Auto or Manual)
Team Entity → Team Leaderboard
Individual Users → Individual Leaderboard
```

## MVP Recommendation

Prioritize:
1. **Schema Standardization** (Cleanup)
2. **Named Teams with Rosters** (New capability)
3. **Improved Match Recording** (UX improvement)

Defer: **League/Season support** (Wait for stable team model)

## Sources
- Competitive analysis of DUPR, Pickleball.com, and generic sports apps.
