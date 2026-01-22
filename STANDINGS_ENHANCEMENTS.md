# Standings Calculator Enhancements

## Overview
Enhanced the standings calculator to support filtering, sorting by individual stats, and provide detailed pitching calculation validation. This addresses issues with standings calculations and adds powerful new features for analyzing team performance.

## Problems Addressed

### 1. Lack of Filtering and Sorting
**Problem:** Could only view standings sorted by total points, no way to see who leads in specific categories.

**Solution:** Added filtering and sorting capabilities to view standings by any stat.

### 2. Pitching Stats Calculation Concerns
**Problem:** Uncertainty about whether pitching stats (ERA, WHIP, K, WQS, SHOLDS) were calculated correctly, especially with IP minimum/maximum rules.

**Solution:** Added detailed validation endpoint that shows exactly how pitching stats are calculated for each team.

### 3. No Individual Stat Rankings
**Problem:** Couldn't easily see "who has the most home runs" or "who has the best ERA".

**Solution:** Added individual stat ranking endpoint that ranks teams by any category.

## New Features

### 1. Individual Stat Rankings
Get rankings for any stat across all teams.

**API Endpoint:**
```
GET /api/standings/stat/<stat>?limit=<n>
```

**Parameters:**
- `stat`: Category to rank by (HR, ERA, K, etc.)
- `limit` (optional): Limit number of results

**Example:**
```bash
# Get top 5 teams by home runs
GET /api/standings/stat/HR?limit=5

# Get all teams ranked by ERA
GET /api/standings/stat/ERA
```

**Response:**
```json
{
  "success": true,
  "stat": "HR",
  "rankings": [
    {
      "team_name": "Team A",
      "value": 245.5,
      "rank": 1,
      "ip": 1200.0,
      "below_ip_minimum": false
    },
    ...
  ]
}
```

### 2. Filtered and Sorted Standings
Get standings with custom filtering and sorting.

**API Endpoint:**
```
GET /api/standings/filtered?sort_by=<stat>&filter_category=<cat>&filter_min=<min>&filter_max=<max>
```

**Parameters:**
- `sort_by` (optional): Category to sort by (default: total_points)
- `filter_category` (optional): Category to filter on
- `filter_min` (optional): Minimum value for filter
- `filter_max` (optional): Maximum value for filter

**Examples:**
```bash
# Sort standings by home runs
GET /api/standings/filtered?sort_by=HR

# Show only teams with ERA below 4.00
GET /api/standings/filtered?filter_category=ERA&filter_max=4.00

# Show teams with 200+ strikeouts, sorted by K
GET /api/standings/filtered?sort_by=K&filter_category=K&filter_min=200
```

**Response:**
```json
{
  "success": true,
  "standings": [...],
  "filter_applied": true,
  "sort_by": "HR",
  "categories": {
    "batting": ["HR", "OBP", "R", "RBI", "SB"],
    "pitching": ["ERA", "K", "SHOLDS", "WHIP", "WQS"]
  }
}
```

### 3. Pitching Calculation Validation
Get detailed breakdown of how pitching stats are calculated.

**API Endpoint:**
```
GET /api/standings/validate-pitching
```

**Response:**
```json
{
  "success": true,
  "validation": {
    "Team A": {
      "total_ip": 1250.5,
      "meets_ip_minimum": true,
      "exceeds_ip_maximum": false,
      "team_era": 3.85,
      "team_whip": 1.22,
      "total_k": 1450,
      "scaled_k": 1450,
      "total_wqs": 185,
      "scaled_wqs": 185,
      "total_sholds": 125.5,
      "scaled_sholds": 125.5,
      "pitcher_count": 9,
      "pitcher_details": [
        {
          "name": "Pitcher Name",
          "position": "SP",
          "ip": 180.0,
          "era": 3.50,
          "whip": 1.15,
          "k": 200,
          "w": 12,
          "qs": 18,
          "sv": 0,
          "hd": 0
        },
        ...
      ]
    }
  }
}
```

## Pitching Stats Calculation Details

### IP (Innings Pitched)
1. Uses `projected_innings_pitched` if available
2. Falls back to `projected_quality_starts * 6.5` (average IP per QS)
3. Falls back to `projected_saves * 1.0` (relief pitchers)
4. Final fallback: 150 IP for SP, 60 IP for RP

### IP Minimum (1000 IP)
- Teams below 1000 IP get **1 point (worst)** in ALL pitching categories
- This is a league rule to ensure teams draft enough pitchers
- Affects: ERA, WHIP, K, SHOLDS, WQS

### IP Maximum (1400 IP)
- Teams exceeding 1400 IP have counting stats scaled down proportionally
- Scale factor = 1400 / total_ip
- Scaled stats: K, W, QS, SV, HD (and derived: WQS, SHOLDS)
- ERA and WHIP are also scaled (IP-weighted averages)

### ERA (Earned Run Average)
- Calculated as IP-weighted average across all pitchers
- Formula: `sum(pitcher_era * pitcher_ip) / total_ip`
- Lower is better (rank 1 = lowest ERA = 13 points)

### WHIP (Walks + Hits per Inning Pitched)
- Calculated as IP-weighted average across all pitchers
- Formula: `sum(pitcher_whip * pitcher_ip) / total_ip`
- Lower is better (rank 1 = lowest WHIP = 13 points)

### K (Strikeouts)
- Sum of all pitcher strikeouts
- Scaled if team exceeds 1400 IP
- Higher is better (rank 1 = most K = 13 points)

### WQS (Wins + Quality Starts)
- Formula: `total_wins + total_quality_starts`
- Scaled if team exceeds 1400 IP
- Higher is better (rank 1 = most WQS = 13 points)

### SHOLDS (Saves + Holds * 0.5)
- Formula: `total_saves + (total_holds * 0.5)`
- Scaled if team exceeds 1400 IP
- Higher is better (rank 1 = most SHOLDS = 13 points)

## Implementation Details

### StandingsCalculatorEnhanced Class
**Location:** `src/services/standings_calculator_enhanced.py`

**New Methods:**

1. **`get_individual_stat_rankings(team_rosters, stat, limit=None)`**
   - Returns rankings for a specific stat
   - Handles IP minimum for pitching stats
   - Sorts correctly (lower better for ERA/WHIP, higher better for others)

2. **`get_filtered_standings(team_rosters, sort_by, filter_category, filter_min_value, filter_max_value)`**
   - Returns filtered and sorted standings
   - Supports custom sorting by any category
   - Supports min/max value filtering

3. **`get_category_leaders(team_rosters, category, top_n=5)`**
   - Convenience method to get top N teams in a category
   - Wrapper around `get_individual_stat_rankings`

4. **`validate_pitching_calculations(team_rosters)`**
   - Returns detailed breakdown of pitching calculations
   - Shows raw totals, scaled totals, and per-pitcher details
   - Useful for debugging and understanding calculations

### API Endpoints
**Location:** `src/api/app.py`

Added three new endpoints:
1. `GET /api/standings/stat/<stat>` - Individual stat rankings
2. `GET /api/standings/filtered` - Filtered and sorted standings
3. `GET /api/standings/validate-pitching` - Pitching calculation validation

## Testing

### Test Coverage
Created comprehensive test suite in `tests/test_standings_enhanced.py`:

1. **test_individual_stat_rankings** - Basic stat ranking functionality
2. **test_individual_stat_rankings_with_limit** - Top N rankings
3. **test_era_rankings_lower_is_better** - ERA/WHIP sorting logic
4. **test_filtered_standings_sort_by_hr** - Custom sorting
5. **test_filtered_standings_with_min_filter** - Minimum value filtering
6. **test_filtered_standings_with_max_filter** - Maximum value filtering
7. **test_category_leaders** - Category leaders functionality
8. **test_validate_pitching_calculations** - Validation endpoint
9. **test_pitching_ip_minimum_handling** - IP minimum logic
10. **test_pitching_ip_maximum_scaling** - IP maximum scaling
11. **test_standings_calculation_consistency** - Consistency checks
12. **test_all_categories_have_rankings** - Complete category coverage
13. **test_category_points_sum_correctly** - Points calculation accuracy

### Test Results
✅ All 13 tests passing
✅ Comprehensive coverage of new features
✅ Validates pitching calculation logic

## Usage Examples

### Example 1: View Home Run Leaders
```bash
curl http://localhost:5000/api/standings/stat/HR?limit=5
```

**Use Case:** See which teams have the most home runs

### Example 2: Find Teams with Best ERA
```bash
curl http://localhost:5000/api/standings/stat/ERA
```

**Use Case:** See which teams have the best pitching (lowest ERA)

### Example 3: Filter Teams by Strikeouts
```bash
curl "http://localhost:5000/api/standings/filtered?sort_by=K&filter_category=K&filter_min=1000"
```

**Use Case:** Show only teams with 1000+ strikeouts, sorted by K

### Example 4: Validate Pitching Calculations
```bash
curl http://localhost:5000/api/standings/validate-pitching
```

**Use Case:** Debug pitching stats, see exactly how ERA/WHIP/K are calculated

### Example 5: Sort Standings by Stolen Bases
```bash
curl "http://localhost:5000/api/standings/filtered?sort_by=SB"
```

**Use Case:** See which teams are best at stealing bases

## Benefits

1. **Better Analysis:** Can now analyze standings from multiple perspectives
2. **Transparency:** Pitching validation shows exactly how stats are calculated
3. **Flexibility:** Filter and sort by any stat to find insights
4. **Debugging:** Easy to verify calculations are correct
5. **Strategy:** Identify strengths and weaknesses in specific categories

## Backward Compatibility

### Maintained
- Original `/api/standings` endpoint unchanged
- All existing functionality preserved
- New features are additive (new endpoints)
- No breaking changes to existing code

### New Endpoints
- `/api/standings/stat/<stat>` - New
- `/api/standings/filtered` - New
- `/api/standings/validate-pitching` - New

## Future Enhancements

Potential improvements for future versions:
1. Add UI components for filtering/sorting standings
2. Add historical tracking of category rankings over time
3. Add category trend analysis (improving/declining)
4. Add "what-if" scenarios for draft picks
5. Add export functionality for standings data
6. Add comparison view (compare two teams side-by-side)

## Pitching Calculation Verification

To verify pitching calculations are correct:

1. **Check IP totals:**
   ```bash
   curl http://localhost:5000/api/standings/validate-pitching
   ```
   Look at `total_ip` for each team

2. **Verify IP minimum:**
   - Teams with `meets_ip_minimum: false` should get 1 point in all pitching categories
   - Check `total_ip` < 1000

3. **Verify IP maximum:**
   - Teams with `exceeds_ip_maximum: true` should have scaled stats
   - Check `scaled_k` < `total_k` when IP > 1400

4. **Verify ERA/WHIP:**
   - Should be IP-weighted averages
   - Formula: `sum(pitcher_stat * pitcher_ip) / total_ip`

5. **Verify counting stats:**
   - K, W, QS, SV, HD should be simple sums
   - Scaled down if IP > 1400

---

**Implementation Date:** January 21, 2026
**Status:** ✅ Implemented and Tested
**Tests:** 13/13 passing
**Backward Compatibility:** ✅ Maintained
**New API Endpoints:** 3
