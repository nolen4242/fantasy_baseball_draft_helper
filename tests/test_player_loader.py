"""Property-based tests for PlayerLoader using Hypothesis.

Tests validate correctness properties from the design document (Properties 1–4).
"""
import string

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.models.player import Player
from src.services.player_loader import PlayerLoader


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

VALID_POSITIONS = ["C", "1B", "2B", "3B", "SS", "OF", "SP", "RP", "RF", "LF", "CF", "DH"]
VALID_DRAFT_POSITIONS = {"C", "1B", "2B", "3B", "SS", "OF", "SP", "RP", "P", "U"}

# Strategy for blended projection dicts (batter fields)
batter_blended_st = st.fixed_dictionaries({
    "projected_home_runs": st.floats(min_value=0, max_value=60, allow_nan=False, allow_infinity=False),
    "projected_obp": st.floats(min_value=0.150, max_value=0.500, allow_nan=False, allow_infinity=False),
    "projected_runs": st.floats(min_value=0, max_value=150, allow_nan=False, allow_infinity=False),
    "projected_rbi": st.floats(min_value=0, max_value=160, allow_nan=False, allow_infinity=False),
    "projected_stolen_bases": st.floats(min_value=0, max_value=80, allow_nan=False, allow_infinity=False),
})

# Strategy for blended projection dicts (pitcher fields)
pitcher_blended_st = st.fixed_dictionaries({
    "projected_wins": st.floats(min_value=0, max_value=25, allow_nan=False, allow_infinity=False),
    "projected_quality_starts": st.floats(min_value=0, max_value=30, allow_nan=False, allow_infinity=False),
    "projected_strikeouts": st.floats(min_value=0, max_value=350, allow_nan=False, allow_infinity=False),
    "projected_era": st.floats(min_value=1.0, max_value=8.0, allow_nan=False, allow_infinity=False),
    "projected_whip": st.floats(min_value=0.7, max_value=2.0, allow_nan=False, allow_infinity=False),
    "projected_saves": st.floats(min_value=0, max_value=50, allow_nan=False, allow_infinity=False),
    "projected_holds": st.floats(min_value=0, max_value=35, allow_nan=False, allow_infinity=False),
    "projected_innings_pitched": st.floats(min_value=0, max_value=250, allow_nan=False, allow_infinity=False),
})

# Combined blended strategy (either batter or pitcher or both)
blended_st = st.one_of(batter_blended_st, pitcher_blended_st)

# Player ID strategy — simple lowercase alphanumeric strings
player_id_st = st.text(
    alphabet=string.ascii_lowercase + string.digits + "_",
    min_size=3,
    max_size=30,
).filter(lambda s: s[0].isalpha())

# Player name strategy
player_name_st = st.text(
    alphabet=string.ascii_letters + " .-",
    min_size=2,
    max_size=40,
).filter(lambda s: s.strip() != "")

# ADP strategies
adp_st = st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False)
optional_adp_st = st.one_of(st.none(), adp_st)

# Savant season stats strategy
savant_season_st = st.fixed_dictionaries({
    "pa": st.floats(min_value=0, max_value=700, allow_nan=False, allow_infinity=False),
    "ab": st.floats(min_value=0, max_value=650, allow_nan=False, allow_infinity=False),
    "h": st.floats(min_value=0, max_value=250, allow_nan=False, allow_infinity=False),
    "hr": st.floats(min_value=0, max_value=60, allow_nan=False, allow_infinity=False),
    "avg": st.floats(min_value=0.100, max_value=0.400, allow_nan=False, allow_infinity=False),
    "xwoba": st.floats(min_value=0.200, max_value=0.500, allow_nan=False, allow_infinity=False),
    "exit_velo": st.floats(min_value=80.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    "barrel_rate": st.floats(min_value=0.0, max_value=25.0, allow_nan=False, allow_infinity=False),
    "sprint_speed": st.floats(min_value=23.0, max_value=31.0, allow_nan=False, allow_infinity=False),
})

# Savant history strategy — dict of year -> stats under a player type key
savant_history_st = st.fixed_dictionaries({
    "batters": st.dictionaries(
        keys=st.sampled_from(["2021", "2022", "2023", "2024", "2025"]),
        values=savant_season_st,
        min_size=1,
        max_size=3,
    ),
})


# ---------------------------------------------------------------------------
# Shared loader instance
# ---------------------------------------------------------------------------

loader = PlayerLoader()


# ---------------------------------------------------------------------------
# Property 1: Player loading round-trip
# ---------------------------------------------------------------------------
# Feature: recommendation-engine-rebuild, Property 1: Player loading round-trip
# **Validates: Requirement 1.1**

@given(
    name=player_name_st,
    player_id=player_id_st,
    position=st.sampled_from(VALID_POSITIONS),
    blended=blended_st,
    team=st.text(alphabet=string.ascii_uppercase, min_size=2, max_size=4),
)
@settings(max_examples=100)
def test_player_loading_round_trip(name, player_id, position, blended, team):
    """For any valid entry with a blended key, the resulting Player's projection
    fields match the blended values."""
    entry = {
        "name": name,
        "player_id": player_id,
        "position": position,
        "team": team,
        "blended": blended,
    }

    player = loader._create_player(entry)

    # Every field present in blended should match the Player attribute
    for field, value in blended.items():
        assert getattr(player, field) == value, (
            f"Mismatch on {field}: expected {value}, got {getattr(player, field)}"
        )


# ---------------------------------------------------------------------------
# Property 2: ADP resolution priority
# ---------------------------------------------------------------------------
# Feature: recommendation-engine-rebuild, Property 2: ADP resolution priority
# **Validates: Requirements 1.2, 1.3**

@given(
    nfbc_adp=optional_adp_st,
    cbs_adp=optional_adp_st,
)
@settings(max_examples=100)
def test_adp_resolution_priority(nfbc_adp, cbs_adp):
    """Resolved ADP equals nfbc_adp when present, else cbs_adp, else None."""
    entry = {}
    if nfbc_adp is not None:
        entry["nfbc_adp"] = nfbc_adp
    if cbs_adp is not None:
        entry["cbs_adp"] = cbs_adp

    result = loader._resolve_adp(entry)

    if nfbc_adp is not None:
        assert result == float(nfbc_adp)
    elif cbs_adp is not None:
        assert result == float(cbs_adp)
    else:
        assert result is None


# ---------------------------------------------------------------------------
# Property 3: Savant data keyed by player ID
# ---------------------------------------------------------------------------
# Feature: recommendation-engine-rebuild, Property 3: Savant data keyed by player ID
# **Validates: Requirements 1.5, 5.8**

@given(
    player_id=player_id_st,
    name=player_name_st,
    savant_history=savant_history_st,
)
@settings(max_examples=100)
def test_savant_data_keyed_by_player_id(player_id, name, savant_history):
    """For entries with savant history, savant_data contains the player_id key
    with most recent season stats."""
    entry = {
        "name": name,
        "player_id": player_id,
        "position": "OF",
        "team": "NYY",
        "savant_history": savant_history,
    }

    # Extract savant via the loader method
    savant = loader._extract_savant(entry)

    # Determine the expected most recent year
    all_years = []
    for _ptype, seasons in savant_history.items():
        if isinstance(seasons, dict):
            all_years.extend(seasons.keys())

    assert len(all_years) > 0, "Strategy should always produce at least one season"
    most_recent_year = max(all_years)

    # The extracted savant should be the stats from the most recent year
    assert savant is not None
    # Find which player type contains the most recent year
    for _ptype, seasons in savant_history.items():
        if most_recent_year in seasons:
            expected = seasons[most_recent_year]
            assert savant == expected
            break


# ---------------------------------------------------------------------------
# Property 4: Position mapping preserves valid draft positions
# ---------------------------------------------------------------------------
# Feature: recommendation-engine-rebuild, Property 4: Position mapping preserves valid draft positions
# **Validates: Requirement 1.6**

@given(position=st.sampled_from(VALID_POSITIONS))
@settings(max_examples=100)
def test_position_mapping_preserves_valid_draft_positions(position):
    """Mapped positions are always valid draft positions, and OF variants map to OF."""
    mapped = loader._map_position(position)

    assert mapped in VALID_DRAFT_POSITIONS, (
        f"Position '{position}' mapped to '{mapped}' which is not a valid draft position"
    )

    # OF variants must map to OF
    if position in ("RF", "LF", "CF"):
        assert mapped == "OF", f"{position} should map to OF, got {mapped}"

    # DH must map to U
    if position == "DH":
        assert mapped == "U", f"DH should map to U, got {mapped}"


# ===========================================================================
# Unit tests for PlayerLoader
# Requirements validated: 1.1, 1.2, 1.3, 1.4, 1.6
# ===========================================================================


class TestPlayerLoaderLoadFromFile:
    """Unit tests that load actual data/master_players.json."""

    def setup_method(self):
        self.loader = PlayerLoader()
        self.players, self.savant_data = self.loader.load("data/master_players.json")
        self._player_map = {p.player_id: p for p in self.players}

    def test_loads_nonempty_player_list(self):
        """Requirement 1.1 — loader produces a non-empty list of Player instances."""
        assert len(self.players) > 0
        assert all(isinstance(p, Player) for p in self.players)

    def test_aaron_judge_projection_fields(self):
        """Requirement 1.1 — Aaron Judge's blended projections are loaded correctly."""
        judge = self._player_map["aaron_judge"]
        assert judge.name == "Aaron Judge"
        assert judge.position == "OF"  # RF mapped to OF
        assert judge.team == "NYY"
        assert judge.projected_home_runs == 44.0
        assert judge.projected_obp == pytest.approx(0.4183)
        assert judge.projected_runs == 109.0
        assert judge.projected_rbi == pytest.approx(108.3333)
        assert judge.projected_stolen_bases == 9.0

    def test_aaron_judge_adp_uses_nfbc(self):
        """Requirement 1.2 — nfbc_adp is preferred when both ADPs are present."""
        judge = self._player_map["aaron_judge"]
        assert judge.adp == pytest.approx(1.97)


class TestMissingBlendedData:
    """Requirement 1.4 — entries without blended projections still produce a Player."""

    def setup_method(self):
        self.loader = PlayerLoader()

    def test_missing_blended_produces_none_projections(self):
        entry = {
            "name": "Test Player",
            "player_id": "test_player",
            "position": "SS",
            "team": "TST",
        }
        player = self.loader._create_player(entry)
        assert player.name == "Test Player"
        assert player.player_id == "test_player"
        assert player.projected_home_runs is None
        assert player.projected_obp is None
        assert player.projected_runs is None
        assert player.projected_rbi is None
        assert player.projected_stolen_bases is None
        assert player.projected_era is None
        assert player.projected_whip is None

    def test_real_player_without_blended(self):
        """Leo De Vries has no blended key in the data file."""
        players, _ = self.loader.load("data/master_players.json")
        leo = next((p for p in players if p.player_id == "leo_de_vries"), None)
        assert leo is not None
        assert leo.projected_home_runs is None
        assert leo.projected_obp is None


class TestADPFallback:
    """Requirements 1.2, 1.3 — ADP resolution with fallback logic."""

    def setup_method(self):
        self.loader = PlayerLoader()

    def test_cbs_adp_fallback_when_nfbc_missing(self):
        entry = {"cbs_adp": 50.0, "nfbc_adp": None}
        assert self.loader._resolve_adp(entry) == 50.0

    def test_cbs_adp_fallback_when_nfbc_absent(self):
        entry = {"cbs_adp": 123.0}
        assert self.loader._resolve_adp(entry) == 123.0

    def test_nfbc_preferred_over_cbs(self):
        entry = {"nfbc_adp": 10.0, "cbs_adp": 20.0}
        assert self.loader._resolve_adp(entry) == 10.0

    def test_none_when_both_missing(self):
        entry = {}
        assert self.loader._resolve_adp(entry) is None

    def test_real_player_cbs_only(self):
        """Leo De Vries has cbs_adp=50.0 and nfbc_adp=None in the data file."""
        players, _ = self.loader.load("data/master_players.json")
        leo = next(p for p in players if p.player_id == "leo_de_vries")
        assert leo.adp == 50.0


class TestPositionMapping:
    """Requirement 1.6 — position mapping for RF, LF, CF, DH."""

    def setup_method(self):
        self.loader = PlayerLoader()

    def test_rf_maps_to_of(self):
        assert self.loader._map_position("RF") == "OF"

    def test_lf_maps_to_of(self):
        assert self.loader._map_position("LF") == "OF"

    def test_cf_maps_to_of(self):
        assert self.loader._map_position("CF") == "OF"

    def test_dh_maps_to_u(self):
        assert self.loader._map_position("DH") == "U"

    def test_standard_positions_pass_through(self):
        for pos in ["C", "1B", "2B", "3B", "SS", "SP", "RP"]:
            assert self.loader._map_position(pos) == pos

    def test_real_players_position_mapping(self):
        """Verify actual players from the data file get correct mapped positions."""
        players, _ = self.loader.load("data/master_players.json")
        pm = {p.player_id: p for p in players}
        # Aaron Judge: RF -> OF
        assert pm["aaron_judge"].position == "OF"
        # Juan Soto: LF -> OF
        assert pm["juan_soto"].position == "OF"
        # Julio Rodriguez: CF -> OF
        assert pm["julio_rodriguez"].position == "OF"
        # Shohei Ohtani: DH -> U
        assert pm["shohei_ohtani"].position == "U"
