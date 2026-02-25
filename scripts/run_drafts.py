#!/usr/bin/env python3
"""Run N full auto-drafts and compare standings results."""
import sys
import random
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.data_loader import DataLoader
from src.services.master_player_dict import MasterPlayerDict
from src.services.draft_service import DraftService
from src.services.recommendation_engine import RecommendationEngine
from src.services.standings_calculator import StandingsCalculator
from src.services.draft_order import DraftOrder
from src.services.team_service import TeamService
from src.services.cleanup_service import CleanupService
from src.models.player import Player

NUM_DRAFTS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
MY_TEAM = "Runtime Terror"


def load_players() -> list[Player]:
    dl = DataLoader()
    mpd = MasterPlayerDict()
    hitters = dl.load_players_from_csv("cbs-batter-2025.csv", file_type="batters")
    pitchers = dl.load_players_from_csv("cbs-pitchers-2025.csv", file_type="pitchers")
    mpd.merge_cbs_data(hitters, player_type="batters")
    mpd.merge_cbs_data(pitchers, player_type="pitchers")
    steamer_h = dl.load_players_from_csv("steamer-batters.csv", file_type="batters")
    steamer_p = dl.load_players_from_csv("steamer-pitchers.csv", file_type="pitchers")
    mpd.merge_steamer_projections(steamer_h, player_type="batters")
    mpd.merge_steamer_projections(steamer_p, player_type="pitchers")
    mpd.load_adp_data()
    players = (
        mpd.get_players_with_projections(player_type="batters")
        + mpd.get_players_with_projections(player_type="pitchers")
    )
    return players


def run_single_draft(all_players: list[Player], draft_num: int) -> dict:
    cleanup = CleanupService()
    cleanup.cleanup_everything(keep_latest_draft=False)

    ds = DraftService()
    draft = ds.create_draft(
        draft_id=f"sim_{draft_num}",
        league_name="Bob Uecker League",
        total_teams=13,
        roster_size=21,
        my_team_name=MY_TEAM,
    )

    rec_engine = RecommendationEngine(ds, all_players)
    ts = TeamService()
    total_picks = draft.total_teams * draft.roster_size

    for pick_num in range(1, total_picks + 1):
        team = DraftOrder.get_team_for_pick(pick_num, draft.total_teams)
        available = ds.get_available_players(all_players, draft)
        if not available:
            break

        if team == MY_TEAM:
            team_players = ds.get_my_team_players(all_players, draft)
            recs = rec_engine.get_recommendations(
                available_players=available,
                my_team=team_players,
                draft_state=draft,
                top_n=1,
                use_ml=False,
            )
            if recs:
                player = recs[0]["player"]
            else:
                player = available[0]
        else:
            team_players = ds.get_team_players(all_players, team, draft)
            recs = rec_engine.get_recommendations_for_team(
                available_players=available,
                team_players=team_players,
                draft_state=draft,
                team_name=team,
                top_n=10,
                use_ml=False,
            )

            current_pick = len(draft.picks) + 1
            adp_range = [
                p for p in available
                if p.adp is not None and abs(p.adp - current_pick) <= 15
            ]
            if not adp_range:
                adp_range = available

            weighted_pool = []
            ai_ids = {r["player"].player_id for r in recs}
            for p in adp_range:
                if not ts.has_available_slot_for_player(team, p):
                    continue
                if p.player_id in ai_ids:
                    weighted_pool.extend([p] * 2)
                else:
                    weighted_pool.append(p)

            if not weighted_pool:
                for p in available:
                    if ts.has_available_slot_for_player(team, p):
                        weighted_pool.append(p)

            if not weighted_pool:
                player = available[0]
            else:
                player = random.choice(weighted_pool)

        ds.draft_player(
            player_id=player.player_id,
            team_name=team,
            player=player,
            draft=draft,
        )

    calc = StandingsCalculator()
    team_rosters_players = {}
    for t_name, p_ids in draft.team_rosters.items():
        team_rosters_players[t_name] = [
            p for p in all_players if p.player_id in p_ids
        ]

    standings = calc.calculate_standings(team_rosters_players)
    return standings


def main():
    print(f"Loading player data...")
    all_players = load_players()
    print(f"Loaded {len(all_players)} players.\n")

    results = []
    rt_wins = 0

    for i in range(1, NUM_DRAFTS + 1):
        print(f"--- Draft {i}/{NUM_DRAFTS} ---")
        standings = run_single_draft(all_players, i)

        winner = standings["final_rankings"][0]
        rt_rank = standings["final_rankings"].index(MY_TEAM) + 1
        rt_pts = standings["total_points"][MY_TEAM]
        rt_bat = standings["batting_points"][MY_TEAM]
        rt_pit = standings["pitching_points"][MY_TEAM]

        results.append({
            "draft": i,
            "winner": winner,
            "rt_rank": rt_rank,
            "rt_points": rt_pts,
            "standings": standings,
        })

        if winner == MY_TEAM:
            rt_wins += 1

        print(f"  Winner: {winner}  |  {MY_TEAM} rank: {rt_rank}  |  Bat: {rt_bat:.1f}  Pitch: {rt_pit:.1f}  Total: {rt_pts:.1f}")
        top3 = standings["final_rankings"][:3]
        for rank, t in enumerate(top3, 1):
            tp = standings["total_points"][t]
            bp = standings["batting_points"][t]
            pp = standings["pitching_points"][t]
            print(f"    #{rank} {t} (Bat: {bp:.1f}  Pitch: {pp:.1f}  Total: {tp:.1f})")

    print(f"\n{'='*60}")
    print(f"RESULTS SUMMARY ({NUM_DRAFTS} drafts)")
    print(f"{'='*60}")
    print(f"{MY_TEAM} wins: {rt_wins}/{NUM_DRAFTS} ({rt_wins/NUM_DRAFTS*100:.0f}%)")
    ranks = [r["rt_rank"] for r in results]
    print(f"Average rank: {sum(ranks)/len(ranks):.1f}")
    print(f"Best rank: {min(ranks)}  |  Worst rank: {max(ranks)}")

    from collections import Counter
    rank_dist = Counter(ranks)
    print(f"\nRank distribution:")
    for rank in sorted(rank_dist):
        print(f"  Rank {rank}: {rank_dist[rank]}x")

    cats = StandingsCalculator.BATTING_CATEGORIES + StandingsCalculator.PITCHING_CATEGORIES
    print(f"\nCategory points (last draft):")
    last = results[-1]["standings"]
    for cat in cats:
        pts = last["category_points"][cat].get(MY_TEAM, 0)
        val = last["category_totals"][MY_TEAM].get(cat, 0)
        print(f"  {cat:>6}: {pts:5.1f} pts  (value: {val:.3f})")


if __name__ == "__main__":
    main()
