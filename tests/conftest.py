"""Pytest configuration and fixtures for tests."""
import pytest
from src.services.cleanup_service import CleanupService


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """
    Automatically clean up team rosters and draft files after each test.
    
    This fixture runs automatically (autouse=True) after each test to ensure
    test data doesn't persist between test runs.
    """
    # Setup: nothing needed before test
    yield
    
    # Teardown: clean up after test
    cleanup = CleanupService()
    cleanup.cleanup_everything(keep_latest_draft=False)


@pytest.fixture
def cleanup_service():
    """Provide a cleanup service instance for tests."""
    return CleanupService()


@pytest.fixture
def cleanup_manual():
    """
    Manual cleanup fixture for tests that need to control when cleanup happens.
    
    Usage:
        def test_something(cleanup_manual):
            # ... do test ...
            cleanup_manual.cleanup_everything()
    """
    return CleanupService()


# ---------------------------------------------------------------------------
# Hypothesis strategies and shared fixtures for property-based testing
# ---------------------------------------------------------------------------
import string
from typing import List, Dict, Optional

from hypothesis import strategies as st, given, settings
from hypothesis.strategies import composite

from src.models.player import Player
from src.models.draft import DraftState, DraftPick

# Valid positions used across the draft system
HITTER_POSITIONS = ["C", "1B", "2B", "3B", "SS", "OF", "U"]
PITCHER_POSITIONS = ["SP", "RP"]
ALL_POSITIONS = HITTER_POSITIONS + PITCHER_POSITIONS

# Weight keys used by the recommendation engine
WEIGHT_KEYS = [
    "zscore", "var", "savant", "position_scarcity", "team_needs",
    "relative_advantage", "adp_value", "pitcher_caps", "category_balance",
]

# Approximate position distribution weights for realistic pools
_POSITION_WEIGHTS = {
    "C": 0.06, "1B": 0.08, "2B": 0.08, "3B": 0.08, "SS": 0.08,
    "OF": 0.25, "U": 0.02, "SP": 0.22, "RP": 0.13,
}


@composite
def player_strategy(draw) -> Player:
    """Generate a random Player instance with valid projection ranges."""
    position = draw(st.sampled_from(ALL_POSITIONS))
    player_id = draw(
        st.text(alphabet=string.ascii_lowercase + string.digits + "_",
                min_size=3, max_size=20)
    )
    name = draw(
        st.text(alphabet=string.ascii_letters + " ", min_size=2, max_size=30)
    )
    team = draw(
        st.text(alphabet=string.ascii_uppercase, min_size=2, max_size=4)
    )

    is_hitter = position in HITTER_POSITIONS

    if is_hitter:
        player = Player(
            player_id=player_id,
            name=name,
            position=position,
            team=team,
            age=draw(st.integers(min_value=20, max_value=42)),
            projected_home_runs=draw(st.floats(min_value=0, max_value=50,
                                               allow_nan=False, allow_infinity=False)),
            projected_obp=draw(st.floats(min_value=0.200, max_value=0.450,
                                         allow_nan=False, allow_infinity=False)),
            projected_runs=draw(st.floats(min_value=20, max_value=130,
                                          allow_nan=False, allow_infinity=False)),
            projected_rbi=draw(st.floats(min_value=20, max_value=140,
                                         allow_nan=False, allow_infinity=False)),
            projected_stolen_bases=draw(st.floats(min_value=0, max_value=60,
                                                   allow_nan=False, allow_infinity=False)),
            adp=draw(st.one_of(st.none(), st.floats(min_value=1.0, max_value=300.0,
                                                     allow_nan=False, allow_infinity=False))),
        )
    else:
        player = Player(
            player_id=player_id,
            name=name,
            position=position,
            team=team,
            age=draw(st.integers(min_value=20, max_value=42)),
            projected_era=draw(st.floats(min_value=2.0, max_value=6.0,
                                         allow_nan=False, allow_infinity=False)),
            projected_strikeouts=draw(st.floats(min_value=30, max_value=300,
                                                 allow_nan=False, allow_infinity=False)),
            projected_saves=draw(st.floats(min_value=0, max_value=45,
                                           allow_nan=False, allow_infinity=False)),
            projected_holds=draw(st.floats(min_value=0, max_value=30,
                                           allow_nan=False, allow_infinity=False)),
            projected_whip=draw(st.floats(min_value=0.90, max_value=1.70,
                                          allow_nan=False, allow_infinity=False)),
            projected_wins=draw(st.floats(min_value=0, max_value=20,
                                          allow_nan=False, allow_infinity=False)),
            projected_quality_starts=draw(st.floats(min_value=0, max_value=25,
                                                     allow_nan=False, allow_infinity=False)),
            projected_innings_pitched=draw(st.floats(min_value=30, max_value=220,
                                                      allow_nan=False, allow_infinity=False)),
            adp=draw(st.one_of(st.none(), st.floats(min_value=1.0, max_value=300.0,
                                                     allow_nan=False, allow_infinity=False))),
        )
    return player


@composite
def player_pool_strategy(draw, min_size: int = 50, max_size: int = 200) -> List[Player]:
    """Generate a list of 50–200 players with realistic position distributions."""
    pool_size = draw(st.integers(min_value=min_size, max_value=max_size))
    players: List[Player] = []
    seen_ids: set = set()

    for i in range(pool_size):
        # Pick position weighted by realistic distribution
        position = draw(st.sampled_from(
            [pos for pos, w in _POSITION_WEIGHTS.items()
             for _ in range(int(w * 100))]
        ))
        is_hitter = position in HITTER_POSITIONS

        pid = f"player_{i}"
        seen_ids.add(pid)

        if is_hitter:
            p = Player(
                player_id=pid,
                name=f"Hitter {i}",
                position=position,
                team="TM",
                projected_home_runs=draw(st.floats(min_value=0, max_value=50,
                                                    allow_nan=False, allow_infinity=False)),
                projected_obp=draw(st.floats(min_value=0.200, max_value=0.450,
                                              allow_nan=False, allow_infinity=False)),
                projected_runs=draw(st.floats(min_value=20, max_value=130,
                                               allow_nan=False, allow_infinity=False)),
                projected_rbi=draw(st.floats(min_value=20, max_value=140,
                                              allow_nan=False, allow_infinity=False)),
                projected_stolen_bases=draw(st.floats(min_value=0, max_value=60,
                                                       allow_nan=False, allow_infinity=False)),
                adp=draw(st.one_of(st.none(), st.floats(min_value=1.0, max_value=300.0,
                                                         allow_nan=False, allow_infinity=False))),
            )
        else:
            p = Player(
                player_id=pid,
                name=f"Pitcher {i}",
                position=position,
                team="TM",
                projected_era=draw(st.floats(min_value=2.0, max_value=6.0,
                                              allow_nan=False, allow_infinity=False)),
                projected_strikeouts=draw(st.floats(min_value=30, max_value=300,
                                                     allow_nan=False, allow_infinity=False)),
                projected_saves=draw(st.floats(min_value=0, max_value=45,
                                                allow_nan=False, allow_infinity=False)),
                projected_holds=draw(st.floats(min_value=0, max_value=30,
                                                allow_nan=False, allow_infinity=False)),
                projected_whip=draw(st.floats(min_value=0.90, max_value=1.70,
                                               allow_nan=False, allow_infinity=False)),
                projected_wins=draw(st.floats(min_value=0, max_value=20,
                                               allow_nan=False, allow_infinity=False)),
                projected_quality_starts=draw(st.floats(min_value=0, max_value=25,
                                                         allow_nan=False, allow_infinity=False)),
                projected_innings_pitched=draw(st.floats(min_value=30, max_value=220,
                                                          allow_nan=False, allow_infinity=False)),
                adp=draw(st.one_of(st.none(), st.floats(min_value=1.0, max_value=300.0,
                                                         allow_nan=False, allow_infinity=False))),
            )
        players.append(p)

    return players


@composite
def savant_strategy(draw) -> Dict[str, float]:
    """Generate a random Savant stat dict with realistic ranges."""
    return {
        "xwoba": draw(st.floats(min_value=0.250, max_value=0.450,
                                 allow_nan=False, allow_infinity=False)),
        "barrel_rate": draw(st.floats(min_value=2.0, max_value=25.0,
                                       allow_nan=False, allow_infinity=False)),
        "exit_velo": draw(st.floats(min_value=82.0, max_value=98.0,
                                     allow_nan=False, allow_infinity=False)),
        "sprint_speed": draw(st.floats(min_value=24.0, max_value=31.0,
                                        allow_nan=False, allow_infinity=False)),
        "avg": draw(st.floats(min_value=0.180, max_value=0.340,
                               allow_nan=False, allow_infinity=False)),
        "obp": draw(st.floats(min_value=0.250, max_value=0.430,
                               allow_nan=False, allow_infinity=False)),
        "slg": draw(st.floats(min_value=0.300, max_value=0.650,
                               allow_nan=False, allow_infinity=False)),
        "hard_hit_pct": draw(st.floats(min_value=25.0, max_value=65.0,
                                        allow_nan=False, allow_infinity=False)),
    }


@composite
def draft_state_strategy(draw, max_picks: int = 200) -> DraftState:
    """Generate a DraftState with 0–max_picks picks made."""
    total_teams = draw(st.integers(min_value=8, max_value=16))
    roster_size = draw(st.integers(min_value=15, max_value=25))
    num_picks = draw(st.integers(min_value=0, max_value=max_picks))

    team_names = [f"Team_{i}" for i in range(total_teams)]
    my_team = team_names[0]

    picks: List[DraftPick] = []
    team_rosters: Dict[str, List[str]] = {t: [] for t in team_names}

    for pick_num in range(1, num_picks + 1):
        round_num = ((pick_num - 1) // total_teams) + 1
        team_idx = (pick_num - 1) % total_teams
        team_name = team_names[team_idx]
        pid = f"drafted_{pick_num}"

        picks.append(DraftPick(
            pick_number=pick_num,
            round=round_num,
            team_name=team_name,
            player_id=pid,
        ))
        team_rosters[team_name].append(pid)

    current_round = ((num_picks) // total_teams) + 1
    current_pick_in_round = (num_picks % total_teams) + 1

    return DraftState(
        draft_id=f"draft_{draw(st.integers(min_value=1, max_value=9999))}",
        league_name="Test League",
        total_teams=total_teams,
        roster_size=roster_size,
        my_team_name=my_team,
        current_pick=current_pick_in_round,
        current_round=current_round,
        picks=picks,
        team_rosters=team_rosters,
    )


@composite
def weights_strategy(draw) -> Dict[str, float]:
    """Generate a random weight dict with values 0.0–2.0."""
    return {
        key: draw(st.floats(min_value=0.0, max_value=2.0,
                             allow_nan=False, allow_infinity=False))
        for key in WEIGHT_KEYS
    }


# ---------------------------------------------------------------------------
# Shared pytest fixtures using the strategies above
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_player_pool():
    """Provide a deterministic small player pool for unit tests."""
    hitters = []
    for i, pos in enumerate(["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"]):
        hitters.append(Player(
            player_id=f"hitter_{i}",
            name=f"Test Hitter {i}",
            position=pos,
            team="TST",
            projected_home_runs=15.0 + i * 3,
            projected_obp=0.300 + i * 0.01,
            projected_runs=60.0 + i * 5,
            projected_rbi=55.0 + i * 5,
            projected_stolen_bases=5.0 + i * 2,
            adp=float(10 + i * 10),
        ))
    pitchers = []
    for i, pos in enumerate(["SP", "SP", "SP", "RP", "RP"]):
        pitchers.append(Player(
            player_id=f"pitcher_{i}",
            name=f"Test Pitcher {i}",
            position=pos,
            team="TST",
            projected_era=3.50 - i * 0.2,
            projected_strikeouts=150.0 + i * 20,
            projected_saves=0.0 if pos == "SP" else 15.0 + i * 5,
            projected_holds=0.0 if pos == "SP" else 10.0 + i * 3,
            projected_whip=1.20 - i * 0.05,
            projected_wins=10.0 + i * 2 if pos == "SP" else 3.0,
            projected_quality_starts=12.0 + i * 2 if pos == "SP" else 0.0,
            projected_innings_pitched=180.0 + i * 10 if pos == "SP" else 65.0,
            adp=float(20 + i * 15),
        ))
    return hitters + pitchers


@pytest.fixture
def sample_draft_state():
    """Provide a deterministic DraftState for unit tests."""
    return DraftState(
        draft_id="test_draft_1",
        league_name="Test League",
        total_teams=13,
        roster_size=21,
        my_team_name="Team_0",
        current_pick=1,
        current_round=1,
        picks=[],
        team_rosters={f"Team_{i}": [] for i in range(13)},
    )


@pytest.fixture
def sample_savant_data():
    """Provide deterministic Savant data keyed by player_id."""
    return {
        "hitter_0": {
            "xwoba": 0.350, "barrel_rate": 12.0, "exit_velo": 90.5,
            "sprint_speed": 27.5, "avg": 0.280, "obp": 0.340,
            "slg": 0.480, "hard_hit_pct": 42.0,
        },
        "pitcher_0": {
            "xwoba": 0.290, "barrel_rate": 6.5, "exit_velo": 86.0,
            "sprint_speed": 27.0, "avg": 0.220, "obp": 0.280,
            "slg": 0.370, "hard_hit_pct": 30.0,
        },
    }


@pytest.fixture
def sample_weights():
    """Provide the default weight dict for unit tests."""
    return {
        "zscore": 1.0,
        "var": 1.0,
        "savant": 0.5,
        "position_scarcity": 0.8,
        "team_needs": 1.0,
        "relative_advantage": 0.7,
        "adp_value": 0.9,
        "pitcher_caps": 1.0,
        "category_balance": 0.6,
    }
