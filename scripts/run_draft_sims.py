"""Run N full draft simulations and report results.

Your team (Runtime Terror) uses the AI recommendation engine.
Opponents draft from an ADP-based pool with some randomness.

Usage:
    python3 -m scripts.run_draft_sims
"""
import sys
import random
import time
from pathlib import Path
from copy import deepcopy

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.player import Player
from src.models.draft import DraftState, DraftPick
from src.services.draft_order import DraftOrder
from src.services.player_loader import PlayerLoader
from src.services.recommendation_engine import RecommendationEngine
from src.services.standings_calculator import StandingsCalculator
from src.services.team_service import TeamService

NUM_SIMS = 20
MY_TEAM = "Runtime Terror"
TOTAL_TEAMS = 13
ROSTER_SIZE = 21


# ---------------------------------------------------------------------------
# Lightweight in-memory draft (no file I/O)
# ---------------------------------------------------------------------------

class InMemoryTeamService:
    """Minimal team service that tracks roster slots in memory only."""

    POSITION_REQUIREMENTS = TeamService.POSITION_REQUIREMENTS

    def __init__(self):
        # team_name -> {pos: [player_id or None, ...]}
        self.rosters = {}

    def init_team(self, team_name):
        self.rosters[team_name] = {
            pos: [None] * count
            for pos, count in self.POSITION_REQUIREMENTS.items()
        }

    def _eligible(self, player: Player):
        pos = player.position.upper()
        eligible = []
        if pos in ('C', '1B', '2B', '3B', 'SS', 'OF'):
            eligible.append(pos)
        if pos in ('SP', 'RP', 'P'):
            eligible.append('P')
        if pos in ('2B', 'SS'):
            eligible.append('MI')
        if pos in ('1B', '3B'):
            eligible.append('CI')
        if pos not in ('SP', 'RP', 'P'):
            eligible.append('U')
        eligible.append('BENCH')
        return eligible

    PRIORITY = ['C', '1B', '2B', '3B', 'SS', 'OF', 'P', 'MI', 'CI', 'U', 'BENCH']

    def has_slot(self, team_name, player):
        slots = self.rosters.get(team_name)
        if not slots:
            return True
        for pos in self._eligible(player):
            if pos in slots and None in slots[pos]:
                return True
        return False

    def assign(self, team_name, player):
        slots = self.rosters[team_name]
        for pos in self.PRIORITY:
            if pos not in self._eligible(player):
                continue
            for i, v in enumerate(slots[pos]):
                if v is None:
                    slots[pos][i] = player.player_id
                    return pos
        return None


class SimDraft:
    """Runs one full draft simulation in memory."""

    def __init__(self, all_players, savant_data):
        self.all_players = all_players
        self.savant_data = savant_data
        self.player_map = {p.player_id: p for p in all_players}
        self.drafted_ids = set()
        self.team_rosters = {t: [] for t in DraftOrder.get_all_teams()}
        self.picks = []  # list of DraftPick
        self.ts = InMemoryTeamService()
        for t in DraftOrder.get_all_teams():
            self.ts.init_team(t)

    # -- helpers --
    def _available(self):
        return [p for p in self.all_players if p.player_id not in self.drafted_ids]

    def _team_players(self, team_name):
        return [self.player_map[pid] for pid in self.team_rosters[team_name]]

    def _make_draft_state(self):
        ds = DraftState(
            draft_id="sim",
            league_name="Sim",
            total_teams=TOTAL_TEAMS,
            roster_size=ROSTER_SIZE,
            my_team_name=MY_TEAM,
        )
        ds.picks = list(self.picks)
        ds.team_rosters = {t: list(ids) for t, ids in self.team_rosters.items()}
        return ds

    def _draft_player(self, team_name, player):
        pick = DraftPick(
            pick_number=len(self.picks) + 1,
            round=(len(self.picks) // TOTAL_TEAMS) + 1,
            team_name=team_name,
            player_id=player.player_id,
        )
        self.picks.append(pick)
        self.drafted_ids.add(player.player_id)
        self.team_rosters[team_name].append(player.player_id)
        self.ts.assign(team_name, player)

    # -- opponent pick logic --
    def _opponent_pick(self, team_name, current_pick, engine):
        """Opponents use the AI engine too, but pick from top-3 with randomness."""
        available = self._available()
        ds = self._make_draft_state()
        team_players = self._team_players(team_name)
        recs = engine.get_recommendations_for_team(
            available_players=available,
            team_players=team_players,
            draft_state=ds,
            team_name=team_name,
            top_n=10,
        )
        # Pick randomly from top 3 recommendations that have a slot
        eligible_recs = [r for r in recs if self.ts.has_slot(team_name, r['player'])]
        if eligible_recs:
            pool = eligible_recs[:3]
            chosen = random.choice(pool)
            return chosen['player']
        # Fallback: ADP-based
        candidates = [p for p in available if self.ts.has_slot(team_name, p)]
        if not candidates:
            return None
        candidates.sort(key=lambda p: (p.adp is None, p.adp or 9999))
        return candidates[0]

    # -- AI pick --
    def _ai_pick(self, engine, team_name):
        available = self._available()
        ds = self._make_draft_state()
        my_team = self._team_players(team_name)
        recs = engine.get_recommendations(
            available_players=available,
            my_team=my_team,
            draft_state=ds,
            top_n=10,
        )
        # Pick the top recommendation that has a slot
        for rec in recs:
            p = rec['player']
            if self.ts.has_slot(team_name, p):
                return p, rec['score'], rec['reasoning']
        # Fallback: best ADP available with slot
        available.sort(key=lambda p: (p.adp is None, p.adp or 9999))
        for p in available:
            if self.ts.has_slot(team_name, p):
                return p, 0.0, "fallback"
        return None, 0.0, ""

    def run(self):
        """Run the full draft. Returns (my_picks_log, all_team_rosters_as_players)."""
        from src.services.draft_service import DraftService
        mock_ds = DraftService.__new__(DraftService)
        mock_ds.current_draft = self._make_draft_state()
        mock_ds.team_service = self.ts
        mock_ds.data_dir = Path("/dev/null")

        engine = RecommendationEngine(
            draft_service=mock_ds,
            players=self.all_players,
            savant_data=self.savant_data,
        )

        my_picks_log = []
        total_picks = TOTAL_TEAMS * ROSTER_SIZE

        for pick_num in range(1, total_picks + 1):
            team = DraftOrder.get_team_for_pick(pick_num, TOTAL_TEAMS)
            # Update mock draft state for engine
            mock_ds.current_draft = self._make_draft_state()

            if team == MY_TEAM:
                player, score, reasoning = self._ai_pick(engine, team)
                if player is None:
                    break
                self._draft_player(team, player)
                rd = (pick_num - 1) // TOTAL_TEAMS + 1
                my_picks_log.append({
                    'pick': pick_num,
                    'round': rd,
                    'player': player,
                    'score': score,
                    'reasoning': reasoning,
                })
            else:
                player = self._opponent_pick(team, pick_num, engine)
                if player is None:
                    break
                self._draft_player(team, player)

        # Build final rosters as Player lists
        final_rosters = {}
        for t, ids in self.team_rosters.items():
            final_rosters[t] = [self.player_map[pid] for pid in ids if pid in self.player_map]

        return my_picks_log, final_rosters


# ---------------------------------------------------------------------------
# Main: run sims and report
# ---------------------------------------------------------------------------

def run_sims():
    print(f"Loading players...")
    loader = PlayerLoader()
    all_players, savant_data = loader.load()
    print(f"Loaded {len(all_players)} players.\n")

    calc = StandingsCalculator()
    results = []

    for sim_num in range(1, NUM_SIMS + 1):
        t0 = time.time()
        sim = SimDraft(all_players, savant_data)
        my_picks, final_rosters = sim.run()
        elapsed = time.time() - t0

        standings = calc.calculate_standings(final_rosters)
        rankings = standings['final_rankings']
        my_rank = rankings.index(MY_TEAM) + 1
        my_points = standings['total_points'][MY_TEAM]
        winner = rankings[0]
        winner_pts = standings['total_points'][winner]

        # Identify value picks and reaches in my draft
        value_picks = []
        reach_picks = []
        for entry in my_picks:
            p = entry['player']
            if p.adp is not None:
                fallen = entry['pick'] - p.adp
                if fallen >= 10:
                    value_picks.append((p.name, p.position, p.adp, entry['pick'], fallen))
                elif fallen <= -10:
                    reach_picks.append((p.name, p.position, p.adp, entry['pick'], fallen))

        results.append({
            'sim': sim_num,
            'rank': my_rank,
            'points': my_points,
            'winner': winner,
            'winner_pts': winner_pts,
            'my_picks': my_picks,
            'value_picks': value_picks,
            'reach_picks': reach_picks,
            'elapsed': elapsed,
            'standings': standings,
        })

        # Print summary line
        win_marker = " *** WIN ***" if my_rank == 1 else ""
        print(f"Sim {sim_num:2d}: Rank {my_rank:2d}/13  |  {my_points:5.1f} pts  |  "
              f"Values: {len(value_picks)}  Reaches: {len(reach_picks)}  |  "
              f"{elapsed:.1f}s{win_marker}")

    # ---------------------------------------------------------------------------
    # Aggregate report
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"DRAFT SIMULATION RESULTS ({NUM_SIMS} sims)")
    print("=" * 70)

    wins = sum(1 for r in results if r['rank'] == 1)
    top3 = sum(1 for r in results if r['rank'] <= 3)
    top5 = sum(1 for r in results if r['rank'] <= 5)
    avg_rank = sum(r['rank'] for r in results) / len(results)
    avg_pts = sum(r['points'] for r in results) / len(results)
    best_rank = min(r['rank'] for r in results)
    worst_rank = max(r['rank'] for r in results)

    print(f"\nWins:       {wins}/{NUM_SIMS} ({wins/NUM_SIMS*100:.0f}%)")
    print(f"Top 3:      {top3}/{NUM_SIMS} ({top3/NUM_SIMS*100:.0f}%)")
    print(f"Top 5:      {top5}/{NUM_SIMS} ({top5/NUM_SIMS*100:.0f}%)")
    print(f"Avg Rank:   {avg_rank:.1f}")
    print(f"Best Rank:  {best_rank}")
    print(f"Worst Rank: {worst_rank}")
    print(f"Avg Points: {avg_pts:.1f}")

    # Rank distribution
    print(f"\nRank Distribution:")
    rank_counts = {}
    for r in results:
        rank_counts[r['rank']] = rank_counts.get(r['rank'], 0) + 1
    for rank in sorted(rank_counts.keys()):
        bar = "█" * rank_counts[rank]
        print(f"  {rank:2d}: {bar} ({rank_counts[rank]})")

    # Most common first-round picks
    print(f"\nRound 1 Picks (your #1 overall):")
    r1_counts = {}
    for r in results:
        if r['my_picks']:
            name = r['my_picks'][0]['player'].name
            r1_counts[name] = r1_counts.get(name, 0) + 1
    for name, count in sorted(r1_counts.items(), key=lambda x: -x[1]):
        print(f"  {name}: {count}x")

    # Notable value picks across all sims
    all_values = []
    for r in results:
        for v in r['value_picks']:
            all_values.append(v)
    if all_values:
        print(f"\nBest Value Picks (fallen 10+ picks past ADP):")
        all_values.sort(key=lambda x: -x[4])  # sort by fallen desc
        seen = set()
        count = 0
        for name, pos, adp, pick, fallen in all_values:
            if name not in seen and count < 10:
                print(f"  {name} ({pos}) - ADP {adp:.0f}, picked at {pick} (fallen {fallen:.0f})")
                seen.add(name)
                count += 1

    # Notable reaches
    all_reaches = []
    for r in results:
        for v in r['reach_picks']:
            all_reaches.append(v)
    if all_reaches:
        print(f"\nWorst Reaches (picked 10+ before ADP):")
        all_reaches.sort(key=lambda x: x[4])  # sort by fallen asc (most negative)
        seen = set()
        count = 0
        for name, pos, adp, pick, fallen in all_reaches:
            if name not in seen and count < 10:
                print(f"  {name} ({pos}) - ADP {adp:.0f}, picked at {pick} ({fallen:.0f} early)")
                seen.add(name)
                count += 1

    # Category strengths/weaknesses
    print(f"\nCategory Performance (avg rank across {NUM_SIMS} sims):")
    all_cats = calc.BATTING_CATEGORIES + calc.PITCHING_CATEGORIES
    cat_ranks = {cat: [] for cat in all_cats}
    for r in results:
        for cat in all_cats:
            rankings = r['standings']['category_rankings'].get(cat, [])
            try:
                cat_ranks[cat].append(rankings.index(MY_TEAM) + 1)
            except ValueError:
                cat_ranks[cat].append(13)
    for cat in all_cats:
        avg = sum(cat_ranks[cat]) / len(cat_ranks[cat])
        best = min(cat_ranks[cat])
        worst = max(cat_ranks[cat])
        label = "BAT" if cat in calc.BATTING_CATEGORIES else "PIT"
        print(f"  {cat:6s} ({label}): avg {avg:4.1f}  best {best:2d}  worst {worst:2d}")

    # Print one detailed sim example (the best one)
    best_sim = min(results, key=lambda r: r['rank'])
    print(f"\n{'=' * 70}")
    print(f"BEST SIM DETAIL (Sim {best_sim['sim']}, Rank {best_sim['rank']})")
    print(f"{'=' * 70}")
    for entry in best_sim['my_picks']:
        p = entry['player']
        adp_str = f"ADP {p.adp:.0f}" if p.adp else "no ADP"
        print(f"  R{entry['round']:2d} Pick {entry['pick']:3d}: {p.name:25s} {p.position:3s} "
              f"({adp_str}) Score: {entry['score']:.1f}")

    print(f"\nTotal sim time: {sum(r['elapsed'] for r in results):.1f}s")


if __name__ == "__main__":
    run_sims()
