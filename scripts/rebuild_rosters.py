"""Rebuild all team roster.json files from the draft JSON."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from src.services.draft_order import DraftOrder
from src.services.team_service import TeamService
from src.services.player_loader import PlayerLoader

# Load players
loader = PlayerLoader()
all_players, _ = loader.load()
player_lookup = {p.player_id: p for p in all_players}

# Load draft
draft_path = Path("data/teams/draft_1773878841.json")
with open(draft_path) as f:
    draft = json.load(f)

picks = draft["picks"]
print(f"Draft has {len(picks)} picks")

# Clean all team folders first
teams_dir = Path("data/teams")
for team_name in DraftOrder.get_all_teams():
    folder = teams_dir / DraftOrder.sanitize_team_name(team_name)
    if folder.exists():
        for f in folder.glob("*.json"):
            f.unlink()
        print(f"  Cleaned {folder.name}")

# Initialize TeamService and rebuild
ts = TeamService()

# Initialize empty rosters for all teams
for team_name in DraftOrder.get_all_teams():
    ts.initialize_team_roster(team_name)

# Replay all picks through TeamService
missing = []
for pick in picks:
    player_id = pick["player_id"]
    team_name = pick["team_name"]
    player = player_lookup.get(player_id)
    
    if not player:
        missing.append(player_id)
        continue
    
    pick_info = {
        "pick_number": pick["pick_number"],
        "round": pick["round"],
        "team_name": team_name
    }
    ts.save_team_pick(team_name, player, pick_info)

if missing:
    print(f"\nMissing players (not in master): {missing}")

# Verify RT roster
rt_roster = ts.get_team_roster("Runtime Terror")
if rt_roster and "positions" in rt_roster:
    print(f"\nRuntime Terror roster from rebuilt roster.json:")
    for pos, slots in rt_roster["positions"].items():
        for slot in slots:
            if slot:
                print(f"  {pos}: {slot['name']} ({slot['player_id']})")

print("\nDone! Restart server to pick up changes.")
