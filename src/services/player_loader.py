"""PlayerLoader service — reads master_players.json and hydrates Player instances."""
import json
import logging
from typing import Dict, List, Optional, Tuple

from src.models.player import Player

logger = logging.getLogger(__name__)


class PlayerLoader:
    """Loads player data from master_players.json into Player instances with Savant data."""

    POSITION_MAP = {
        "RF": "OF",
        "LF": "OF",
        "CF": "OF",
        "DH": "U",
    }

    # Batter projection fields in the blended dict
    BATTER_FIELDS = [
        "projected_home_runs",
        "projected_obp",
        "projected_runs",
        "projected_rbi",
        "projected_stolen_bases",
    ]

    # Pitcher projection fields in the blended dict
    PITCHER_FIELDS = [
        "projected_wins",
        "projected_quality_starts",
        "projected_strikeouts",
        "projected_era",
        "projected_whip",
        "projected_saves",
        "projected_holds",
        "projected_innings_pitched",
    ]

    def load(self, filepath: str = "data/master_players.json") -> Tuple[List[Player], Dict[str, dict]]:
        """Load all players and savant data from the master JSON file.

        Returns:
            players: List of Player instances with blended projections and ADP
            savant_data: Dict keyed by player_id -> most recent savant season dict
        """
        with open(filepath, "r") as f:
            raw = json.load(f)

        players: List[Player] = []
        savant_data: Dict[str, dict] = {}

        for key, entry in raw.items():
            name = entry.get("name")
            player_id = entry.get("player_id")

            if not name or not player_id:
                logger.warning("Skipping entry '%s': missing name or player_id", key)
                continue

            player = self._create_player(entry)
            players.append(player)

            savant = self._extract_savant(entry)
            if savant is not None:
                savant_data[player_id] = savant

        logger.info("Loaded %d players, %d with savant data", len(players), len(savant_data))
        return players, savant_data

    def _create_player(self, entry: dict) -> Player:
        """Map a single JSON entry to a Player dataclass."""
        blended = entry.get("blended")
        position = self._map_position(entry.get("position", ""))
        adp = self._resolve_adp(entry)

        kwargs: dict = {
            "player_id": entry["player_id"],
            "name": entry["name"],
            "position": position,
            "team": entry.get("team", ""),
            "adp": adp,
        }

        if blended:
            for field in self.BATTER_FIELDS + self.PITCHER_FIELDS:
                value = blended.get(field)
                # Treat JSON null as None
                kwargs[field] = value if value is not None else None
        else:
            logger.info("No blended projections for '%s'", entry["name"])

        return Player(**kwargs)

    def _map_position(self, raw_position: str) -> str:
        """Map raw position (RF, LF, CF, DH) to draft position (OF, U, etc.)."""
        return self.POSITION_MAP.get(raw_position, raw_position)

    def _resolve_adp(self, entry: dict) -> Optional[float]:
        """Return nfbc_adp if present, else cbs_adp, else None."""
        nfbc = entry.get("nfbc_adp")
        if nfbc is not None:
            return float(nfbc)
        cbs = entry.get("cbs_adp")
        if cbs is not None:
            return float(cbs)
        return None

    def _extract_savant(self, entry: dict) -> Optional[dict]:
        """Return the most recent season's Savant data dict, or None."""
        history = entry.get("savant_history")
        if not history:
            return None

        # savant_history has a top-level key like "batters" or "pitchers"
        # containing year-keyed season dicts
        most_recent_year = ""
        most_recent_data = None

        for _player_type, seasons in history.items():
            if not isinstance(seasons, dict):
                continue
            for year, stats in seasons.items():
                if year > most_recent_year:
                    most_recent_year = year
                    most_recent_data = stats

        return most_recent_data
