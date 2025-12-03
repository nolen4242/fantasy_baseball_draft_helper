# Bob Uecker Imaginary Baseball League Configuration

This application is configured specifically for the **Bob Uecker Imaginary Baseball League**.

## League Settings

- **Teams:** 13
- **Active Roster Size:** 21 players
- **Reserve:** 1 spot
- **Scoring:** Rotisserie

## Position Requirements

Each active roster must contain:
- 1 C (Catcher)
- 1 1B (First Base)
- 1 2B (Second Base)
- 1 3B (Third Base)
- 1 SS (Shortstop)
- 1 MI (Middle Infielder - 2B or SS)
- 1 CI (Corner Infielder - 1B or 3B)
- 4 OF (Outfielders)
- 1 U (Utility - any offensive position)
- 9 P (Pitchers - any combination of SP/RP)

**Total:** 11 position players + 9 pitchers = 20 active + 1 reserve = 21 total

## Scoring Categories

### Batting (5 categories)
1. **HR** - Home Runs
2. **OBP** - On Base Percentage
3. **R** - Runs
4. **RBI** - Runs Batted In
5. **SB** - Stolen Bases

### Pitching (5 categories)
1. **ERA** - Earned Run Average (lower is better)
2. **K** - Strikeouts
3. **SHOLDS** - Saves + Holds (Holds count as 0.5)
4. **WHIP** - Walks + Hits per Inning Pitched (lower is better)
5. **WQS** - Wins + Quality Starts

## Pitcher Minimums

- **Minimum:** 1,000 innings pitched
- **Maximum:** 1,400 innings pitched
- Teams failing to reach minimum receive zeros in ERA and WHIP
- Teams exceeding maximum stop accruing pitching stats after limit is reached

## Player Eligibility

- Players eligible at primary position + positions with 20+ games played (last year or this year)
- Players can be moved between eligible positions during the season
- Injured players don't count against positional limits
- Minor league players don't count against positional limits

## Draft Settings

- **Draft Type:** Snake draft (21 rounds)
- **Draft Order:** Based on previous season standings (6th-last place picks first, then 5th-1st place)
- **New Teams:** Pick after 1st place team

## Notes for CSV Import

When importing player projections, the following column names are supported:

**Batting:**
- `projected_home_runs` or `hr`
- `projected_obp` or `obp`
- `projected_runs` or `r`
- `projected_rbi` or `rbi`
- `projected_stolen_bases` or `sb`

**Pitching:**
- `projected_wins` or `w`
- `projected_quality_starts` or `qs`
- `projected_strikeouts` or `k` or `so`
- `projected_era` or `era`
- `projected_whip` or `whip`
- `projected_saves` or `sv`
- `projected_holds` or `hld` or `holds`

The recommendation engine will use these categories to calculate player value and provide draft recommendations.

