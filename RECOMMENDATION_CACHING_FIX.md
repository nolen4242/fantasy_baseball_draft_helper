# Recommendation Caching Fix

## Problem
The recommendation engine was recommending the same player every single time because the cache key only considered `(player_id, draft_state_hash)` without accounting for:
1. Changes in available players (when players are drafted)
2. Different teams requesting recommendations
3. Current pick number changes

## Root Cause
The cache key in `RecommendationEngine` was too simplistic:
```python
cache_key = (player.player_id, draft_state_hash)
```

This meant that once a player was evaluated, the cached score would be reused even if:
- Other players were drafted (changing the available player pool)
- A different team was requesting recommendations
- The draft progressed to a new pick

## Solution
Updated the caching logic in `src/services/recommendation_engine.py`:

### 1. Added Available Players Hash
Created `_get_available_players_hash()` method that generates a hash based on the available player pool:
```python
def _get_available_players_hash(self, available_players: List[Player]) -> str:
    """Generate hash of available players for caching."""
    import hashlib
    # Hash based on available player IDs (sorted for consistency)
    player_ids = sorted([p.player_id for p in available_players[:100]])
    players_str = ",".join(player_ids)
    return hashlib.md5(players_str.encode()).hexdigest()[:8]
```

### 2. Updated Draft State Hash
Modified `_get_draft_state_hash()` to include the current pick number:
```python
def _get_draft_state_hash(self, draft_state: DraftState) -> str:
    """Generate hash of draft state for caching."""
    import hashlib
    picks_str = ",".join([f"{p.player_id}:{p.team_name}" for p in draft_state.picks[-50:]])
    # Also include current pick number to ensure cache updates
    picks_str += f"|pick:{len(draft_state.picks)}"
    return hashlib.md5(picks_str.encode()).hexdigest()[:16]
```

### 3. Enhanced Cache Key
Updated the cache key to include all three factors:
```python
draft_state_hash = self._get_draft_state_hash(draft_state)
available_hash = self._get_available_players_hash(available_players)

# Cache key now includes: draft state + available players + team name
cache_state_key = f"{draft_state_hash}:{available_hash}:{team_name}"

# Check if we need to clear cache
if cache_state_key != self._cache_draft_state_hash:
    self._cache.clear()
    self._cache_draft_state_hash = cache_state_key

# Use enhanced cache key for individual player evaluations
cache_key = (player.player_id, cache_state_key)
```

## Testing
Created comprehensive test suite in `tests/test_recommendation_caching.py`:

1. **test_cache_key_includes_available_players_hash** - Verifies cache key includes available players
2. **test_cache_invalidated_when_available_players_change** - Ensures cache clears when players are drafted
3. **test_cache_key_includes_team_name** - Confirms different teams get different cache entries
4. **test_cache_invalidated_when_pick_made** - Validates cache clears when draft progresses
5. **test_available_players_hash_function** - Tests hash function consistency
6. **test_draft_state_hash_includes_pick_number** - Verifies pick number affects hash

All tests passing ✅

## Impact
- Recommendations now update dynamically as players are drafted
- Different teams get appropriate recommendations based on their needs
- Cache still provides performance benefits while maintaining correctness
- No breaking changes to existing functionality

## Files Modified
- `src/services/recommendation_engine.py` - Updated caching logic (lines ~220-250, 293-310)
- `tests/test_recommendation_caching.py` - New comprehensive test suite

## Backward Compatibility
✅ Fully backward compatible - existing code continues to work without changes
