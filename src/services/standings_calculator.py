"""Calculate fantasy roto standings from team rosters."""
from typing import List, Dict, Tuple
from src.models.player import Player


class StandingsCalculator:
    """Calculates rotisserie category standings and final rankings.

    Scoring rules (Bob Uecker Imaginary Baseball League, 13 teams):
      - 10 categories: 5 batting + 5 pitching
      - Counting stats (highest wins): HR, R, RBI, SB, K, WQS, SV
      - Rate stats: OBP (highest wins), ERA (lowest wins), WHIP (lowest wins)
      - Points per category: 13 for 1st, 12 for 2nd … 1 for 13th
      - Ties split the points equally
      - Highest total points = league winner
    """

    BATTING_CATEGORIES = ['HR', 'OBP', 'R', 'RBI', 'SB']
    PITCHING_CATEGORIES = ['ERA', 'K', 'SV', 'WHIP', 'WQS']

    # Categories where LOWER value is better
    LOWER_IS_BETTER = {'ERA', 'WHIP'}

    def calculate_standings(self, team_rosters: Dict[str, List[Player]]) -> Dict:
        """Return full roto standings with batting/pitching breakdowns."""
        num_teams = len(team_rosters)
        if num_teams == 0:
            return {
                'category_totals': {},
                'category_points': {},
                'category_rankings': {},
                'batting_points': {},
                'pitching_points': {},
                'total_points': {},
                'final_rankings': [],
            }

        category_totals: Dict[str, Dict[str, float]] = {}
        for team_name, roster in team_rosters.items():
            category_totals[team_name] = self._calculate_team_totals(roster)

        all_categories = self.BATTING_CATEGORIES + self.PITCHING_CATEGORIES

        # Per-category roto points (with tie handling)
        category_points: Dict[str, Dict[str, float]] = {
            cat: {} for cat in all_categories
        }
        category_rankings: Dict[str, List[str]] = {}

        for cat in all_categories:
            lower_better = cat in self.LOWER_IS_BETTER
            pts, ranked = self._score_category(
                cat, category_totals, num_teams, lower_better
            )
            category_points[cat] = pts
            category_rankings[cat] = ranked

        # Aggregate points
        batting_points: Dict[str, float] = {}
        pitching_points: Dict[str, float] = {}
        total_points: Dict[str, float] = {}

        for team in team_rosters:
            bp = sum(category_points[c].get(team, 0) for c in self.BATTING_CATEGORIES)
            pp = sum(category_points[c].get(team, 0) for c in self.PITCHING_CATEGORIES)
            batting_points[team] = bp
            pitching_points[team] = pp
            total_points[team] = bp + pp

        # Final rankings: highest total points first
        final_rankings = sorted(
            team_rosters.keys(),
            key=lambda t: total_points[t],
            reverse=True,
        )

        return {
            'category_totals': category_totals,
            'category_points': category_points,
            'category_rankings': category_rankings,
            'batting_points': batting_points,
            'pitching_points': pitching_points,
            'total_points': total_points,
            'final_rankings': final_rankings,
        }

    # ------------------------------------------------------------------
    # Category scoring with tie handling
    # ------------------------------------------------------------------

    def _score_category(
        self,
        category: str,
        category_totals: Dict[str, Dict[str, float]],
        num_teams: int,
        lower_is_better: bool,
    ) -> Tuple[Dict[str, float], List[str]]:
        """Score a single category, returning (points_dict, ranked_teams).

        Ties split points: if two teams tie for 3rd in a 13-team league,
        they each get (11 + 10) / 2 = 10.5 instead of one getting 11 and
        the other 10.
        """
        team_values = {
            team: totals.get(category, 0.0)
            for team, totals in category_totals.items()
        }

        # If every team has the same value (e.g. all 0), award 0 points
        # instead of splitting — avoids phantom points before picks are made
        unique_vals = set(team_values.values())
        if len(unique_vals) <= 1:
            points = {t: 0.0 for t in team_values}
            sorted_teams = list(team_values.keys())
            return points, sorted_teams

        # Sort: for lower-is-better, ascending; otherwise descending
        sorted_teams = sorted(
            team_values.keys(),
            key=lambda t: team_values[t],
            reverse=not lower_is_better,
        )

        points: Dict[str, float] = {}
        i = 0
        while i < len(sorted_teams):
            # Find all teams tied at this value
            current_val = team_values[sorted_teams[i]]
            j = i
            while j < len(sorted_teams) and team_values[sorted_teams[j]] == current_val:
                j += 1
            # Positions i..j-1 are tied.  They share the points for those slots.
            # Slot i gets (num_teams - i) points, slot i+1 gets (num_teams - i - 1), etc.
            shared_points = sum(num_teams - k for k in range(i, j)) / (j - i)
            for k in range(i, j):
                points[sorted_teams[k]] = shared_points
            i = j

        return points, sorted_teams

    # ------------------------------------------------------------------
    # Team stat totals
    # ------------------------------------------------------------------

    def _calculate_team_totals(self, roster: List[Player]) -> Dict[str, float]:
        """Calculate category totals for a single team.

        Only the top 11 hitters and top 9 pitchers (by projected value)
        count toward stats.  Any extras are treated as bench and excluded,
        matching the real league rule that bench players don't accumulate
        category stats.
        """
        totals: Dict[str, float] = {
            'HR': 0.0, 'OBP': 0.0, 'R': 0.0, 'RBI': 0.0, 'SB': 0.0,
            'W': 0.0, 'QS': 0.0, 'K': 0.0, 'SV': 0.0,
            'ERA': 0.0, 'WHIP': 0.0,
        }

        MAX_ACTIVE_HITTERS = 12
        MAX_ACTIVE_PITCHERS = 9

        all_hitters = [p for p in roster if p.position not in ('SP', 'RP', 'P')]
        all_pitchers = [p for p in roster if p.position in ('SP', 'RP', 'P')]

        # Rank hitters by composite counting value (HR + R + RBI + SB + OBP*200)
        def _hitter_value(h: Player) -> float:
            return (
                (h.projected_home_runs or 0)
                + (h.projected_runs or 0)
                + (h.projected_rbi or 0)
                + (h.projected_stolen_bases or 0)
                + (h.projected_obp or 0) * 200
            )

        # Rank pitchers by composite value (W + QS + K/10 + SV - ERA - WHIP)
        def _pitcher_value(p: Player) -> float:
            return (
                (p.projected_wins or 0)
                + (p.projected_quality_starts or 0)
                + (p.projected_strikeouts or 0) / 10.0
                + (p.projected_saves or 0)
                - (p.projected_era or 0)
                - (p.projected_whip or 0)
            )

        hitters = sorted(all_hitters, key=_hitter_value, reverse=True)[:MAX_ACTIVE_HITTERS]
        pitchers = sorted(all_pitchers, key=_pitcher_value, reverse=True)[:MAX_ACTIVE_PITCHERS]

        # -- Batting counting stats --
        for h in hitters:
            totals['HR'] += h.projected_home_runs or 0
            totals['R'] += h.projected_runs or 0
            totals['RBI'] += h.projected_rbi or 0
            totals['SB'] += h.projected_stolen_bases or 0

        # OBP: average only over hitters that have OBP data
        obp_values = [h.projected_obp for h in hitters if h.projected_obp]
        totals['OBP'] = sum(obp_values) / len(obp_values) if obp_values else 0.0

        # -- Pitching counting stats --
        for p in pitchers:
            totals['W'] += p.projected_wins or 0
            totals['QS'] += p.projected_quality_starts or 0
            totals['K'] += p.projected_strikeouts or 0
            totals['SV'] += p.projected_saves or 0

        totals['WQS'] = totals['W'] + totals['QS']

        # ERA / WHIP: average only over pitchers that have the data
        era_values = [p.projected_era for p in pitchers if p.projected_era]
        whip_values = [p.projected_whip for p in pitchers if p.projected_whip]
        totals['ERA'] = sum(era_values) / len(era_values) if era_values else 0.0
        totals['WHIP'] = sum(whip_values) / len(whip_values) if whip_values else 0.0

        return totals

    # ------------------------------------------------------------------
    # Legacy helpers (used by recommendation engine)
    # ------------------------------------------------------------------

    def _rank_teams_by_category(
        self, category: str, category_totals: Dict[str, Dict[str, float]]
    ) -> List[str]:
        """Rank teams by a category (best first)."""
        reverse = category not in self.LOWER_IS_BETTER
        return sorted(
            category_totals.keys(),
            key=lambda t: category_totals[t].get(category, 0),
            reverse=reverse,
        )

    def _get_team_rank(
        self, team_name: str, category: str,
        category_rankings: Dict[str, List[str]]
    ) -> int:
        """Get 1-based rank (1 = best)."""
        rankings = category_rankings.get(category, [])
        try:
            return rankings.index(team_name) + 1
        except ValueError:
            return len(rankings) + 1
