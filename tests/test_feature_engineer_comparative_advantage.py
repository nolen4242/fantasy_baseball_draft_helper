from src.models.player import Player
from src.services.feature_engineer import FeatureEngineer


def test_comparative_advantage_counts_all_opponents_ahead_excluding_my_team():
    """
    Regression test:
    Comparative-advantage logic must exclude *my team* by name (draft_state.my_team_name),
    not a hard-coded league team name like "Runtime Terror".
    """
    fe = FeatureEngineer()

    my_team_name = "Dawg"

    # My roster: low totals.
    my_team = [
        Player(
            player_id="me1",
            name="Me Hitter",
            position="OF",
            team="AAA",
            projected_home_runs=10,
            projected_runs=0,
            projected_rbi=0,
            projected_stolen_bases=0,
        )
    ]

    # Candidate player improves HR by +5.
    candidate = Player(
        player_id="cand1",
        name="Candidate",
        position="OF",
        team="BBB",
        projected_home_runs=15,
        projected_runs=0,
        projected_rbi=0,
        projected_stolen_bases=0,
    )

    # Opponents ahead in HR:
    runtime_terror_roster = [
        Player(
            player_id="rt1",
            name="RT Hitter",
            position="OF",
            team="CCC",
            projected_home_runs=20,
            projected_runs=0,
            projected_rbi=0,
            projected_stolen_bases=0,
        )
    ]
    other_roster = [
        Player(
            player_id="o1",
            name="Other Hitter",
            position="OF",
            team="DDD",
            projected_home_runs=30,
            projected_runs=0,
            projected_rbi=0,
            projected_stolen_bases=0,
        )
    ]

    all_team_rosters = {
        my_team_name: my_team,
        "Runtime Terror": runtime_terror_roster,
        "Other": other_roster,
    }

    features = fe._extract_comparative_advantage(
        player=candidate,
        my_team=my_team,
        all_team_rosters=all_team_rosters,
        league_thresholds=None,
        my_team_name=my_team_name,
    )

    # At baseline, my HR = 10. Two opponents ("Runtime Terror" and "Other") are ahead (> 10).
    assert features["passes_hr_opponents"] == 2

