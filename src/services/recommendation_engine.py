"""Recommendation engine for draft picks — slim compositor that delegates to
ZScoreCalculator, ReplacementLevelAnalyzer, and SavantAdjuster."""
from typing import List, Dict, Tuple, Optional
from src.models.player import Player
from src.models.draft import DraftState
from src.services.draft_service import DraftService
from src.services.standings_calculator import StandingsCalculator
from src.services.team_service import TeamService
from src.services.zscore_calculator import ZScoreCalculator
from src.services.replacement_level import ReplacementLevelAnalyzer
from src.services.savant_adjuster import SavantAdjuster


class RecommendationEngine:
    """Provides draft recommendations using z-score valuation, replacement-level
    analysis, Savant adjustments, and 6 additional scoring factors."""

    DEFAULT_WEIGHTS = {
        'zscore': 1.0,
        'var': 1.0,
        'savant': 0.5,
        'position_scarcity': 0.8,
        'team_needs': 1.0,
        'relative_advantage': 0.7,
        'adp_value': 0.9,
        'pitcher_caps': 1.0,
        'category_balance': 0.6,
        'opponent_blocking': 0.35,
    }

    def __init__(self, draft_service: DraftService, players: List[Player] = None,
                 savant_data: Dict[str, dict] = None, weights: Dict[str, float] = None):
        self.draft_service = draft_service
        self.standings_calculator = StandingsCalculator()
        self.team_service = TeamService()
        self.all_players = players or []
        self.savant_data = savant_data or {}
        self.zscore_calc = ZScoreCalculator()
        self.replacement_analyzer = ReplacementLevelAnalyzer()
        self.savant_adjuster = SavantAdjuster()
        self.weights = weights or self.DEFAULT_WEIGHTS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_recommendations(
        self,
        available_players: List[Player],
        my_team: List[Player],
        draft_state: DraftState,
        top_n: int = 10,
        use_ml: bool = True,
    ) -> List[Dict]:
        """Return top_n recommendations sorted by composite score.

        Flow:
        1. Compute z-scores for available players
        2. Compute VAR for available players
        3. Get all team rosters
        4. Filter to players with available roster slots
        5. Score each candidate via _score_player()
        6. Sort by score descending
        7. Return top min(max(top_n, 10), 30) recommendations
        """
        return self.get_recommendations_for_team(
            available_players=available_players,
            team_players=my_team,
            draft_state=draft_state,
            team_name=draft_state.my_team_name,
            top_n=top_n,
        )

    def get_recommendations_for_team(
        self,
        available_players: List[Player],
        team_players: List[Player],
        draft_state: DraftState,
        team_name: str,
        top_n: int = 10,
        use_ml: bool = True,
    ) -> List[Dict]:
        """Get top N draft recommendations for a specific team.

        Computes z-scores and VAR for the undrafted pool, then scores each
        candidate via _score_player().

        Args:
            available_players: Undrafted players.
            team_players: Current roster for the team.
            draft_state: Current draft state.
            team_name: Name of the team to get recommendations for.
            top_n: Number of recommendations to return.

        Returns:
            List of dicts with 'player', 'score', 'reasoning' keys.
        """
        if not available_players:
            return []

        # 1. Compute z-scores for available players
        zscores = self.zscore_calc.calculate(available_players)

        # 2. Compute VAR for available players
        var_scores = self.replacement_analyzer.analyze(available_players, zscores)

        # 3. Get all team rosters for opponent analysis
        all_team_rosters = self._get_all_team_rosters(draft_state)

        # 4. Filter to players with available roster slots
        # Sort available players by ADP first to prioritize evaluation
        sorted_available = sorted(
            available_players,
            key=lambda p: (p.adp is None, p.adp or float('inf'))
        )

        # Evaluate top 150 by ADP
        players_to_evaluate = sorted_available[:150]

        # Also include top 20 pitchers even if they're not in top 150
        pitchers = [p for p in sorted_available if p.position in ['SP', 'RP', 'P']]
        top_pitchers = pitchers[:20]
        for pitcher in top_pitchers:
            if pitcher not in players_to_evaluate:
                players_to_evaluate.append(pitcher)

        # Filter out players that don't have available roster slots
        players_with_slots = []
        for player in players_to_evaluate:
            if self.team_service.has_available_slot_for_player(team_name, player):
                players_with_slots.append(player)

        # If we don't have enough players with available slots, expand search
        if len(players_with_slots) < top_n * 2:
            expanded_evaluate = sorted_available[:300]
            for player in expanded_evaluate:
                if player not in players_to_evaluate:
                    if self.team_service.has_available_slot_for_player(team_name, player):
                        players_with_slots.append(player)
                        if len(players_with_slots) >= top_n * 3:
                            break

        if not players_with_slots:
            return []

        # 5. Score each candidate via _score_player()
        recommendations = []
        for player in players_with_slots:
            try:
                score, reasoning = self._score_player(
                    player, team_players, available_players, draft_state,
                    all_team_rosters, zscores, var_scores, team_name
                )
                recommendations.append({
                    'player': player,
                    'score': score,
                    'reasoning': reasoning,
                })
            except Exception:
                # Skip players that cause scoring errors
                continue

        # 6. Sort by score descending
        recommendations.sort(key=lambda x: x['score'], reverse=True)

        # 7. Return top recommendations
        # Default range is 10-30, but allow larger requests (e.g. for player analysis)
        count = max(top_n, 10)
        return recommendations[:count]

    # ------------------------------------------------------------------
    # Core scoring
    # ------------------------------------------------------------------

    def _score_player(
        self,
        player: Player,
        my_team: List[Player],
        available_players: List[Player],
        draft_state: DraftState,
        all_team_rosters: Dict[str, List[Player]],
        zscores: Dict[str, Dict[str, float]],
        var_scores: Dict[str, float],
        team_name: str,
    ) -> Tuple[float, str]:
        """Compute composite score from 10 weighted factors.

        Each raw factor is normalized to roughly -10..+10 before weighting
        so that no single component dominates the composite.

        Returns:
            (total_score, reasoning_string)
        """
        w = self.weights
        score = 0.0
        reasoning_parts = []

        # 1. Z-score component (already in z-score scale, ~-5 to +10)
        player_zscores = zscores.get(player.player_id, {})
        composite_z = player_zscores.get('composite', 0.0)
        z_component = composite_z * w.get('zscore', 1.0)
        score += z_component
        reasoning_parts.append(f"Z: {composite_z:.2f}")

        # 2. VAR component (already in z-score scale, ~-5 to +10)
        var_value = var_scores.get(player.player_id, 0.0)
        var_component = var_value * w.get('var', 1.0)
        score += var_component
        best_pos = player.position
        reasoning_parts.append(f"VAR: {var_value:.2f} ({best_pos})")

        # 3. Savant component (already small, ~-3 to +3)
        savant_adj, savant_signal = self.savant_adjuster.adjust(
            player, self.savant_data.get(player.player_id)
        )
        savant_component = savant_adj * w.get('savant', 0.5)
        score += savant_component
        if savant_signal:
            reasoning_parts.append(f"Savant: {savant_adj:+.1f} ({savant_signal})")
        else:
            reasoning_parts.append(f"Savant: {savant_adj:+.1f}")

        # 4. Position scarcity — normalize from 0..125 to 0..10
        scarcity_raw, scarcity_reason = self._score_position_scarcity(
            player, my_team, available_players, draft_state, all_team_rosters
        )
        scarcity_norm = max(min(scarcity_raw / 12.5, 10.0), -5.0)
        scarcity_component = scarcity_norm * w.get('position_scarcity', 0.8)
        score += scarcity_component
        if scarcity_reason:
            reasoning_parts.append(f"Scarcity: {scarcity_norm:+.1f} ({scarcity_reason})")

        # 5. Team needs — normalize from -200..615 to -10..+10
        needs_raw, needs_reason = self._score_team_needs(
            player, my_team, draft_state, available_players
        )
        needs_norm = max(min(needs_raw / 60.0, 10.0), -10.0)
        needs_component = needs_norm * w.get('team_needs', 1.0)
        score += needs_component
        if needs_reason:
            reasoning_parts.append(f"Needs: {needs_norm:+.1f} ({needs_reason})")

        # 6. Relative advantage — normalize from 0..80 to 0..10
        relative_raw, relative_reason = self._score_relative_advantage(
            player, my_team, all_team_rosters, draft_state, team_name
        )
        relative_norm = max(min(relative_raw / 8.0, 10.0), -5.0)
        relative_component = relative_norm * w.get('relative_advantage', 0.7)
        score += relative_component
        if relative_reason:
            reasoning_parts.append(f"Advantage: {relative_norm:+.1f} ({relative_reason})")

        # 7. ADP value — normalize from -45..230 to -10..+10
        adp_raw, adp_reason = self._score_adp_value(
            player, draft_state
        )
        adp_norm = max(min(adp_raw / 20.0, 10.0), -10.0)
        adp_component = adp_norm * w.get('adp_value', 0.9)
        score += adp_component
        if adp_reason:
            reasoning_parts.append(f"ADP: {adp_norm:+.1f} ({adp_reason})")

        # 8. Pitcher caps — normalize from -150..60 to -10..+5
        pitcher_cap_raw, pitcher_cap_reason = self._score_pitcher_caps(
            player, my_team, draft_state
        )
        pitcher_cap_norm = max(min(pitcher_cap_raw / 15.0, 5.0), -10.0)
        pitcher_cap_component = pitcher_cap_norm * w.get('pitcher_caps', 1.0)
        score += pitcher_cap_component
        if pitcher_cap_reason:
            reasoning_parts.append(f"PitcherCap: {pitcher_cap_norm:+.1f} ({pitcher_cap_reason})")

        # 9. Category balance — normalize from 0..300 to 0..10
        balance_raw, balance_reason = self._score_category_balance(
            player, my_team, all_team_rosters, team_name
        )
        balance_norm = max(min(balance_raw / 30.0, 10.0), 0.0)
        balance_component = balance_norm * w.get('category_balance', 0.6)
        score += balance_component
        if balance_reason:
            reasoning_parts.append(f"Balance: {balance_norm:+.1f} ({balance_reason})")

        # 10. Opponent blocking — normalize from 0..80 to 0..10
        blocking_raw, blocking_reason = self._score_opponent_blocking(
            player, my_team, all_team_rosters, draft_state, team_name
        )
        blocking_norm = max(min(blocking_raw / 8.0, 10.0), 0.0)
        blocking_component = blocking_norm * w.get('opponent_blocking', 0.35)
        score += blocking_component
        if blocking_reason:
            reasoning_parts.append(f"Block: {blocking_norm:+.1f} ({blocking_reason})")

        reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Solid pick"
        return score, reasoning

    # ------------------------------------------------------------------
    # Roster helpers
    # ------------------------------------------------------------------

    def _get_all_team_rosters(self, draft_state: DraftState) -> Dict[str, List[Player]]:
        """Get all team rosters as Player objects."""
        all_rosters = {}
        for team_name, player_ids in draft_state.team_rosters.items():
            players = [
                p for p in self.all_players
                if p.player_id in player_ids
            ]
            all_rosters[team_name] = players
        return all_rosters

    # ------------------------------------------------------------------
    # Scoring factors (stubs — will be refactored in tasks 6.2–6.7)
    # ------------------------------------------------------------------

    def _score_pitcher_caps(
        self,
        player: Player,
        my_team: List[Player],
        draft_state: DraftState,
    ) -> Tuple[float, str]:
        """Pitcher roster limits and saves needs.

        Applies two adjustments for pitchers:
        1. Roster cap penalties: -40 at 7+ pitchers, -150 at 9+ pitchers
        2. Closer bonuses: tiered by closer count and draft pick thresholds.
        """
        is_pitcher = player.position in ['SP', 'RP', 'P']
        if not is_pitcher:
            return 0.0, ""

        pitcher_count = sum(1 for p in my_team if p.position in ['SP', 'RP', 'P'])
        current_pick = len(draft_state.picks) + 1
        score = 0.0
        reasoning_parts = []

        # Roster cap penalties
        if pitcher_count >= 9:
            score -= 150
            reasoning_parts.append("Roster has enough pitchers")
        elif pitcher_count >= 7:
            score -= 40
            reasoning_parts.append("Have 7+ pitchers")

        # Closer bonus (saves)
        player_saves = player.projected_saves or 0
        if player_saves >= 10:
            closers_on_team = sum(
                1 for p in my_team if (p.projected_saves or 0) >= 10
            )
            if closers_on_team == 0 and current_pick >= 60:
                score += 100
                reasoning_parts.append(f"NEED closer ({int(player_saves)} SV)")
            elif closers_on_team == 1 and current_pick >= 100:
                score += 60
                reasoning_parts.append(f"2nd closer ({int(player_saves)} SV)")
            elif closers_on_team == 2 and current_pick >= 160:
                score += 30
                reasoning_parts.append(f"3rd closer ({int(player_saves)} SV)")

        reasoning = " | ".join(reasoning_parts) if reasoning_parts else ""
        return score, reasoning

    def _score_category_balance(
        self,
        player: Player,
        my_team: List[Player],
        all_team_rosters: Dict[str, List[Player]],
        team_name: str,
    ) -> Tuple[float, str]:
        """Category balance bonus with anti-punt protection.

        Two tiers of protection:
        1. Standard balance (5+ players, losing to 8+ opponents): +30 per weak cat
        2. Anti-punt floor (8+ players): if bottom-3 in any category, strong
           boost (+50) for players improving it.  If already bottom-3 in one
           category, double the boost for a second weak category to prevent
           double-punting.

        Rate categories (ERA, WHIP) are handled as lower-is-better.
        """
        if not all_team_rosters or len(my_team) < 5:
            return 0.0, ""

        score = 0.0
        reasoning_parts = []

        my_totals = self.standings_calculator._calculate_team_totals(my_team)
        projected = self.standings_calculator._calculate_team_totals(my_team + [player])

        # Pre-compute opponent totals once
        opponent_totals: Dict[str, Dict[str, float]] = {}
        for opp_name, opp_roster in all_team_rosters.items():
            if opp_name == team_name:
                continue
            opponent_totals[opp_name] = self.standings_calculator._calculate_team_totals(opp_roster)

        cats_to_check = (
            self.standings_calculator.BATTING_CATEGORIES
            + self.standings_calculator.PITCHING_CATEGORIES
        )

        # Track how many categories we're bottom-3 in (for anti-punt)
        bottom3_cats = []
        cat_opponents_better: Dict[str, int] = {}

        for cat in cats_to_check:
            my_val = my_totals.get(cat, 0)
            lower_is_better = cat in ('ERA', 'WHIP')

            opponents_better = 0
            for opp_totals in opponent_totals.values():
                opp_val = opp_totals.get(cat, 0)
                if lower_is_better:
                    if opp_val > 0 and opp_val < my_val:
                        opponents_better += 1
                else:
                    if opp_val > my_val:
                        opponents_better += 1

            cat_opponents_better[cat] = opponents_better

            # Track bottom-3 categories (10+ opponents better = rank 11-13)
            if opponents_better >= 10:
                bottom3_cats.append(cat)

            # Standard balance: losing to 8+ opponents
            if opponents_better >= 8:
                proj_val = projected.get(cat, 0)
                if lower_is_better:
                    improved = proj_val < my_val
                else:
                    improved = proj_val > my_val
                if improved:
                    score += 30
                    reasoning_parts.append(f"Improves weak {cat} (rank {opponents_better + 1})")

        # --- Anti-punt floor (8+ players) ---
        if len(my_team) >= 8 and bottom3_cats:
            already_punting_one = len(bottom3_cats) >= 1

            for cat in bottom3_cats:
                my_val = my_totals.get(cat, 0)
                proj_val = projected.get(cat, 0)
                lower_is_better = cat in ('ERA', 'WHIP')

                if lower_is_better:
                    improved = proj_val < my_val
                else:
                    improved = proj_val > my_val

                if improved:
                    # Base anti-punt boost
                    boost = 50

                    # If we're already bottom-3 in another category, double
                    # the boost for this one to prevent double-punting
                    if already_punting_one and len(bottom3_cats) >= 2:
                        boost = 100

                    score += boost
                    reasoning_parts.append(
                        f"ANTI-PUNT {cat} (rank {cat_opponents_better[cat] + 1}, +{boost})"
                    )

        reasoning = " | ".join(reasoning_parts) if reasoning_parts else ""
        return score, reasoning

    # ------------------------------------------------------------------
    # Scoring factor methods
    # ------------------------------------------------------------------

    def _score_adp_value(
        self,
        player: Player,
        draft_state: DraftState,
    ) -> Tuple[float, str]:
        """Score ADP value — reward steals, penalize reaches.

        A player still available past their ADP is a value pick (they fell).
        A player picked before their ADP is a reach.

        gap = current_pick - ADP
          positive gap → player has fallen past ADP (value / steal)
          negative gap → picking before ADP (reach)

        Value scoring uses a relevance window (~3 rounds).
        Players whose ADP is far beyond the current pick get diminishing
        credit — a guy at ADP 154 isn't a "value" at pick 1.

        Tiered reach penalties:
          1-3 picks early  → small penalty  (-1 per pick)
          4-9 picks early  → moderate penalty (-2 per pick beyond 3)
          10+ picks early  → large penalty  (-3 per pick beyond 9)

        Returns (0.0, "No ADP data") when ADP is None.
        """
        import math

        current_pick = len(draft_state.picks) + 1
        player_adp = player.adp

        if player_adp is None:
            return 0.0, "No ADP data"

        # How far the player has fallen past their ADP
        # Positive = fallen (value), negative = reaching
        fallen = current_pick - player_adp

        if fallen > 0:
            # Player has fallen past their ADP — value pick / steal
            value_score = fallen * 1.5
            if fallen >= 20:
                label = f"ADP {player_adp:.0f} - steal, fallen {fallen:.0f} picks"
            else:
                label = f"ADP {player_adp:.0f} - value, fallen {fallen:.0f} picks"
            return value_score, label

        if fallen == 0:
            return 0.0, f"ADP {player_adp:.0f} - right at ADP (pick {current_pick})"

        # Negative fallen = reaching (picking before ADP)
        reach = abs(fallen)  # how many picks early we'd be taking them

        # Relevance window: players whose ADP is far ahead aren't really
        # "reaches" — they're just not relevant yet
        window = max(draft_state.total_teams * 3, 20)

        if reach <= 3:
            penalty = -reach * 1.0
            label = f"ADP {player_adp:.0f} - small reach, {reach:.0f} picks early"
        elif reach <= 9:
            penalty = -3.0 + -((reach - 3) * 2.0)
            label = f"ADP {player_adp:.0f} - moderate reach, {reach:.0f} picks early"
        elif reach <= window:
            penalty = -3.0 + -12.0 + -((reach - 9) * 3.0)
            label = f"ADP {player_adp:.0f} - large reach, {reach:.0f} picks early"
        else:
            # Beyond the window — not really a reach, just not relevant yet
            base_penalty = -3.0 + -12.0 + -((window - 9) * 3.0)
            excess = reach - window
            decay_penalty = math.log1p(excess) * -0.5
            penalty = base_penalty + decay_penalty
            label = f"ADP {player_adp:.0f} - available later (pick {current_pick})"

        return penalty, label

    def _score_relative_advantage(
        self,
        player: Player,
        my_team: List[Player],
        all_team_rosters: Dict[str, List[Player]],
        draft_state: DraftState,
        team_name: Optional[str] = None,
    ) -> Tuple[float, str]:
        """Score how much this player improves weak categories relative to opponents.

        Uses StandingsCalculator to rank my team across all 10 scoring categories
        against the other 12 teams, then applies tiered bonuses:
          - Bottom-third (ranks 9-13): larger bonus
          - Middle (ranks 5-8): moderate bonus
          - Top-third (ranks 1-4): smaller bonus
        """
        if team_name is None:
            team_name = draft_state.my_team_name

        if not all_team_rosters or team_name not in all_team_rosters:
            return 0.0, ""

        score = 0.0
        reasoning_parts = []

        # Build rosters dict with my current team and projected team
        rosters_current = dict(all_team_rosters)
        rosters_current[team_name] = my_team

        rosters_projected = dict(all_team_rosters)
        rosters_projected[team_name] = my_team + [player]

        # Use StandingsCalculator to get category totals and rankings
        standings_current = self.standings_calculator.calculate_standings(rosters_current)
        standings_projected = self.standings_calculator.calculate_standings(rosters_projected)

        current_totals = standings_current['category_totals'].get(team_name, {})
        projected_totals = standings_projected['category_totals'].get(team_name, {})

        all_categories = (
            self.standings_calculator.BATTING_CATEGORIES
            + self.standings_calculator.PITCHING_CATEGORIES
        )
        num_teams = len(all_team_rosters)

        for cat in all_categories:
            # Get my current rank in this category (1 = best)
            current_rank = self.standings_calculator._get_team_rank(
                team_name, cat, standings_current['category_rankings']
            )

            current_val = current_totals.get(cat, 0.0)
            projected_val = projected_totals.get(cat, 0.0)

            # Determine if the player improves this category
            if cat in self.standings_calculator.LOWER_IS_BETTER:
                improves = projected_val < current_val
            else:
                improves = projected_val > current_val

            if not improves:
                continue

            # Tiered bonus based on current rank
            if current_rank >= 9:
                # Bottom-third (9th-13th): larger bonus — most room to gain roto points
                bonus = 8.0
                tier = "weak"
            elif current_rank >= 5:
                # Middle (5th-8th): moderate bonus
                bonus = 4.0
                tier = "mid"
            else:
                # Top-third (1st-4th): smaller bonus — diminishing returns
                bonus = 1.5
                tier = "strong"

            score += bonus
            reasoning_parts.append(f"boosts {cat} (rank {current_rank}, {tier})")

        reasoning = ", ".join(reasoning_parts) if reasoning_parts else ""
        return score, reasoning

    def _score_opponent_blocking(
        self,
        player: Player,
        my_team: List[Player],
        all_team_rosters: Dict[str, List[Player]],
        draft_state: DraftState,
        team_name: str,
    ) -> Tuple[float, str]:
        """Score the blocking/hate-draft value of taking this player.

        Only activates after pick 100 when team compositions are clearer.
        Checks if any opponent would get a disproportionate benefit from
        this player — specifically if an opponent is already top-3 in a
        category and this player would extend their lead.

        Kept as a tiebreaker (low weight) so we don't hate-draft players
        we don't need at the expense of our own team building.
        """
        current_pick = len(draft_state.picks) + 1
        if current_pick < 100 or not all_team_rosters:
            return 0.0, ""

        score = 0.0
        reasoning_parts = []

        all_categories = (
            self.standings_calculator.BATTING_CATEGORIES
            + self.standings_calculator.PITCHING_CATEGORIES
        )

        # Get current standings
        standings = self.standings_calculator.calculate_standings(all_team_rosters)
        category_rankings = standings['category_rankings']
        category_totals = standings['category_totals']

        for cat in all_categories:
            ranked_teams = category_rankings.get(cat, [])
            if len(ranked_teams) < 3:
                continue

            lower_is_better = cat in self.standings_calculator.LOWER_IS_BETTER

            # Check top-3 opponents (not us)
            for opp_name in ranked_teams[:3]:
                if opp_name == team_name:
                    continue

                opp_roster = all_team_rosters.get(opp_name, [])
                opp_totals = category_totals.get(opp_name, {})
                opp_val = opp_totals.get(cat, 0)

                # Would this player significantly help this opponent?
                projected_opp = self.standings_calculator._calculate_team_totals(
                    opp_roster + [player]
                )
                proj_val = projected_opp.get(cat, 0)

                if lower_is_better:
                    helps_opponent = proj_val < opp_val
                else:
                    helps_opponent = proj_val > opp_val

                if helps_opponent:
                    # Opponent is already top-3 and this player extends their lead
                    opp_rank = ranked_teams.index(opp_name) + 1
                    if opp_rank == 1:
                        bonus = 20
                    elif opp_rank == 2:
                        bonus = 15
                    else:
                        bonus = 10
                    score += bonus
                    reasoning_parts.append(f"blocks {opp_name} {cat} (rank {opp_rank})")

        # Cap the total blocking score to prevent it from dominating
        score = min(score, 80.0)

        reasoning = ", ".join(reasoning_parts[:3]) if reasoning_parts else ""
        if len(reasoning_parts) > 3:
            reasoning += f" +{len(reasoning_parts) - 3} more"
        return score, reasoning

    def _score_position_scarcity(
        self,
        player: Player,
        my_team: List[Player],
        available_players: List[Player],
        draft_state: DraftState,
        all_team_rosters: Dict[str, List[Player]]
    ) -> Tuple[float, str]:
        """Score position scarcity based on above-average supply vs demand.

        Uses ADP as a proxy for player quality (lower ADP = above-average).
        Compares the count of above-average remaining players to the number
        of teams still needing that position.

        Returns:
            (scarcity_score, reasoning_string)
        """
        player_pos = player.position
        is_pitcher = player_pos in ('SP', 'RP', 'P')

        # --- Flex-aware eligible pool ---
        FLEX_ELIGIBLE = {
            'MI': {'2B', 'SS'},
            'CI': {'1B', '3B'},
            'U': {'C', '1B', '2B', '3B', 'SS', 'OF'},
        }

        if player_pos in FLEX_ELIGIBLE:
            eligible_positions = FLEX_ELIGIBLE[player_pos]
            pool = [p for p in available_players if p.position in eligible_positions or p.position == player_pos]
        elif is_pitcher:
            pool = [p for p in available_players if p.position in ('SP', 'RP', 'P')]
        else:
            pool = [p for p in available_players if p.position == player_pos]

        if not pool:
            return 0.0, ""

        # --- Count above-average players (ADP heuristic: ADP exists and < 300) ---
        above_avg_count = sum(
            1 for p in pool
            if p.adp is not None and p.adp < 300
        )

        # --- Count teams still needing this position ---
        position_requirements = {
            'C': 1, '1B': 1, '2B': 1, '3B': 1, 'SS': 1,
            'MI': 1, 'CI': 1, 'OF': 4, 'U': 1, 'P': 9, 'SP': 9, 'RP': 9,
        }
        required_per_team = position_requirements.get(player_pos, 1)

        teams_needing = 0
        for team_name, roster in all_team_rosters.items():
            if player_pos in FLEX_ELIGIBLE:
                eligible_positions = FLEX_ELIGIBLE[player_pos]
                filled = sum(1 for p in roster if p.position in eligible_positions or p.position == player_pos)
            elif is_pitcher:
                filled = sum(1 for p in roster if p.position in ('SP', 'RP', 'P'))
            else:
                filled = sum(1 for p in roster if p.position == player_pos)
            if filled < required_per_team:
                teams_needing += 1

        # --- Compute scarcity score ---
        if teams_needing == 0:
            # All teams filled — low scarcity
            scarcity_score = 5.0
            reasoning = f"{player_pos}: all teams filled"
        elif above_avg_count == 0:
            # No above-avg players left — high scarcity
            scarcity_score = 100.0
            reasoning = f"{player_pos}: no above-avg left, {teams_needing} teams need"
        else:
            # Ratio: fewer above-avg players per needing team = more scarce
            ratio = above_avg_count / teams_needing
            if ratio < 0.5:
                scarcity_score = 80.0
            elif ratio < 1.0:
                scarcity_score = 60.0
            elif ratio < 2.0:
                scarcity_score = 35.0
            else:
                scarcity_score = 15.0
            reasoning = f"{player_pos}: {above_avg_count} above-avg, {teams_needing} teams need"

        # --- Catcher inherent scarcity bonus ---
        if player_pos == 'C':
            scarcity_score += 25.0
            reasoning += " (C scarce)"

        return scarcity_score, reasoning

    def _score_team_needs(
        self,
        player: Player,
        my_team: List[Player],
        draft_state: DraftState,
        available_players: List[Player]
    ) -> Tuple[float, str]:
        """Score how well this player fills a team roster need.

        Checks roster against required slots:
          - 12 hitter slots: C, 1B, 2B, 3B, SS, MI, CI, 4×OF, U
          - 9 pitcher slots (SP/RP/P)

        Flex eligibility:
          - MI accepts 2B or SS
          - CI accepts 1B or 3B
          - U accepts any hitter

        Returns:
            (score, reasoning_string)
        """
        # Required roster slots
        HITTER_SLOTS = {
            'C': 1, '1B': 1, '2B': 1, '3B': 1, 'SS': 1,
            'MI': 1, 'CI': 1, 'OF': 4, 'U': 1,
        }
        TOTAL_HITTER_SLOTS = sum(HITTER_SLOTS.values())
        TOTAL_PITCHER_SLOTS = 9

        # Flex eligibility mapping
        FLEX_ELIGIBLE = {
            'MI': {'2B', 'SS'},
            'CI': {'1B', '3B'},
            'U': {'C', '1B', '2B', '3B', 'SS', 'OF'},  # any hitter
        }

        PITCHER_POSITIONS = {'SP', 'RP', 'P'}

        player_pos = player.position
        is_pitcher = player_pos in PITCHER_POSITIONS
        is_hitter = not is_pitcher

        # --- Count current roster composition ---
        # Direct position counts
        position_counts = {}
        for pos in list(HITTER_SLOTS.keys()) + ['SP', 'RP', 'P']:
            position_counts[pos] = 0
        for p in my_team:
            if p.position in position_counts:
                position_counts[p.position] = position_counts.get(p.position, 0) + 1

        pitcher_count = sum(1 for p in my_team if p.position in PITCHER_POSITIONS)
        hitter_count = len(my_team) - pitcher_count

        # Track which flex slots are effectively filled
        # A flex slot is filled if we have enough eligible players to cover
        # both the primary slot AND the flex slot
        mi_eligible = sum(1 for p in my_team if p.position in FLEX_ELIGIBLE['MI'])
        ci_eligible = sum(1 for p in my_team if p.position in FLEX_ELIGIBLE['CI'])
        u_eligible = sum(1 for p in my_team if p.position not in PITCHER_POSITIONS)

        # Determine unfilled slots
        # Primary slots filled directly
        unfilled_primary = {}
        for pos, required in HITTER_SLOTS.items():
            if pos in ('MI', 'CI', 'U'):
                continue  # handle flex separately
            filled = min(position_counts.get(pos, 0), required)
            unfilled_primary[pos] = required - filled

        # Flex slot analysis:
        # MI is filled if we have more 2B/SS players than 2B+SS primary slots need
        slots_2b = HITTER_SLOTS['2B']  # 1
        slots_ss = HITTER_SLOTS['SS']  # 1
        mi_primary_used = min(position_counts.get('2B', 0), slots_2b) + min(position_counts.get('SS', 0), slots_ss)
        mi_surplus = mi_eligible - mi_primary_used
        mi_filled = mi_surplus >= 1

        # CI is filled if we have more 1B/3B players than 1B+3B primary slots need
        slots_1b = HITTER_SLOTS['1B']  # 1
        slots_3b = HITTER_SLOTS['3B']  # 1
        ci_primary_used = min(position_counts.get('1B', 0), slots_1b) + min(position_counts.get('3B', 0), slots_3b)
        ci_surplus = ci_eligible - ci_primary_used
        ci_filled = ci_surplus >= 1

        # U is filled if we have more hitters than all other hitter slots need
        other_hitter_slots_needed = sum(v for k, v in HITTER_SLOTS.items() if k != 'U')
        u_filled = u_eligible > other_hitter_slots_needed

        need_score = 0.0
        reasoning_parts = []

        if is_hitter:
            # Check if player fills an unfilled primary position
            primary_unfilled = unfilled_primary.get(player_pos, 0)
            if primary_unfilled > 0:
                need_score += primary_unfilled * 80
                reasoning_parts.append(f"Fills {player_pos} need ({position_counts.get(player_pos, 0)}/{HITTER_SLOTS.get(player_pos, 0)})")
            elif player_pos in HITTER_SLOTS and primary_unfilled <= 0:
                # Position is maxed — negative adjustment (Req 7.3)
                current = position_counts.get(player_pos, 0)
                required = HITTER_SLOTS.get(player_pos, 0)
                if current > required:
                    need_score -= 200
                    reasoning_parts.append(f"REDUNDANT: Already have {current} {player_pos} (need {required})")
                    return need_score, " | ".join(reasoning_parts)
                elif current == required:
                    # Exactly at max — mild negative unless flex helps
                    need_score -= 50
                    reasoning_parts.append(f"Maxed {player_pos}: {current}/{required}")

            # Flex eligibility bonuses (Req 7.4)
            # MI: 2B/SS can fill MI
            if player_pos in FLEX_ELIGIBLE['MI'] and not mi_filled:
                need_score += 40
                reasoning_parts.append("Can fill MI slot")

            # CI: 1B/3B can fill CI
            if player_pos in FLEX_ELIGIBLE['CI'] and not ci_filled:
                need_score += 40
                reasoning_parts.append("Can fill CI slot")

            # U: any hitter can fill U
            if not u_filled:
                need_score += 25
                reasoning_parts.append("Can fill U slot")

            # Overall hitter need
            hitters_needed = TOTAL_HITTER_SLOTS - hitter_count
            if hitters_needed > 0:
                need_score += hitters_needed * 20
                my_picks_remaining = draft_state.roster_size - len(my_team)
                if my_picks_remaining > 0 and hitters_needed > my_picks_remaining / 2:
                    need_score += 50
                    reasoning_parts.append(f"URGENT: Need {hitters_needed} more hitters")
            else:
                need_score -= 60
                reasoning_parts.append("Have enough hitters")

        if is_pitcher:
            pitchers_needed = TOTAL_PITCHER_SLOTS - pitcher_count

            # Req 7.5: Baseline positive score while team has < 9 pitchers
            # Scale comparable to hitter needs so pitchers aren't systematically
            # undervalued. Pitchers are 9/21 active slots — use similar per-slot
            # bonuses as hitters (hitters get ~80 per primary slot + 20 per overall).
            if pitcher_count < TOTAL_PITCHER_SLOTS:
                need_score += pitchers_needed * 40
                if pitchers_needed > 4:
                    need_score += 30
                    reasoning_parts.append(f"Need {pitchers_needed} more pitchers")
                else:
                    reasoning_parts.append(f"Pitcher need ({pitcher_count}/{TOTAL_PITCHER_SLOTS})")

                my_picks_remaining = draft_state.roster_size - len(my_team)
                if my_picks_remaining > 0 and pitchers_needed > my_picks_remaining / 2:
                    need_score += 50
                    reasoning_parts.append(f"URGENT: Need {pitchers_needed} more pitchers")
            else:
                # Maxed pitchers — negative adjustment (Req 7.3)
                need_score -= 100
                reasoning_parts.append("Have enough pitchers")

        # --- Bench-only penalty: don't fill reserve-only picks before active slots ---
        # A player is "bench-only" if all active slots for their type are full.
        # Bench players don't count for stats, so drafting them early is wasteful.
        current_round = (len(draft_state.picks) // draft_state.total_teams) + 1
        active_rounds = TOTAL_HITTER_SLOTS + TOTAL_PITCHER_SLOTS

        if is_hitter and hitter_count >= TOTAL_HITTER_SLOTS:
            if current_round <= active_rounds:
                need_score -= 300
                reasoning_parts.append("BENCH ONLY — save for reserve rounds")
            else:
                reasoning_parts.append("Reserve hitter")
        elif is_pitcher and pitcher_count >= TOTAL_PITCHER_SLOTS:
            if current_round <= active_rounds:
                need_score -= 300
                reasoning_parts.append("BENCH ONLY — save for reserve rounds")
            else:
                reasoning_parts.append("Reserve pitcher")

        reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Depth pick"
        return need_score, reasoning
