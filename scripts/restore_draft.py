"""Restore draft state from known rosters after server restart wiped data.

67 total picks: 5 full rounds (65 picks) + 2 picks into round 6.
FIXED_ROUNDS=3, so:
  R1-R3: fixed order
  R4: snake (reverse)
  R5: snake (normal)  
  R6: snake (reverse) — 2 picks in so far
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import requests

BASE = "http://localhost:5001"

TEAM_PICKS = {
    "Big Sticks": [
        "bryce_harper", "junior_caminero", "julio_rodriguez",
        "jesus_luzardo", "hunter_brown"
    ],
    "Dawg": [
        "fernando_tatis", "james_wood", "shohei_ohtani",
        "max_fried", "edwin_diaz"
    ],
    "Gashouse Gang": [
        "willson_contreras", "jazz_chisholm", "joe_ryan",
        "tarik_skubal", "cade_smith"
    ],
    "Guillotine": [
        "tyler_soderstrom", "gunnar_henderson", "zach_neto",
        "jackson_chourio", "jarren_duran", "logan_gilbert"
    ],
    "Like a Nightmare": [
        "freddie_freeman", "ketel_marte", "manny_machado",
        "jackson_merrill", "paul_skenes"
    ],
    "Long Balls": [
        "nick_kurtz", "eugenio_suarez", "juan_soto",
        "cristopher_sanchez", "mason_miller"
    ],
    "MAGA DOGE": [
        "hunter_goodman", "rafael_devers", "yordan_alvarez",
        "garrett_crochet", "yoshinobu_yamamoto"
    ],
    "Magnum GI": [
        "vladimir_guerrero", "trea_turner", "brent_rooker",
        "kyle_tucker", "andres_munoz"
    ],
    "Rieken Havoc": [
        "jose_ramirez", "francisco_lindor", "wyatt_langford",
        "cody_bellinger", "jhoan_duran", "chris_sale"
    ],
    "Runtime Terror": [
        "pete_alonso", "brice_turang", "corbin_carroll",
        "aaron_judge", "jacob_degrom"
    ],
    "Simba's Dublin Green Sox": [
        "cal_raleigh", "josh_naylor", "bobby_witt",
        "bryan_woo", "cole_ragans"
    ],
    "Trex": [
        "mookie_betts", "pete_crow_armstrong", "ronald_acuna",
        "george_kirby", "logan_webb"
    ],
    "Young Guns": [
        "matt_olson", "austin_riley", "elly_de_la_cruz",
        "roman_anthony", "kyle_schwarber"
    ],
}

TEAM_ORDER = [
    "Runtime Terror", "Dawg", "Long Balls", "Simba's Dublin Green Sox",
    "Young Guns", "Gashouse Gang", "Magnum GI", "Trex",
    "Rieken Havoc", "Guillotine", "MAGA DOGE", "Big Sticks",
    "Like a Nightmare"
]
FIXED_ROUNDS = 3


def get_round_order(round_num):
    if round_num <= FIXED_ROUNDS:
        return TEAM_ORDER[:]
    snake_idx = round_num - FIXED_ROUNDS
    if snake_idx % 2 == 1:
        return list(reversed(TEAM_ORDER))
    return TEAM_ORDER[:]


def load_master_players():
    with open("data/master_players.json") as f:
        return json.load(f)


def get_player_adp(players_dict, player_id):
    for key, p in players_dict.items():
        if p.get("player_id") == player_id:
            return p.get("adp") or 999
    return 999


def reconstruct_pick_order(players_dict):
    # Sort each team's players by ADP (lowest = earliest pick)
    team_queues = {}
    for team, pids in TEAM_PICKS.items():
        adps = [(pid, get_player_adp(players_dict, pid)) for pid in pids]
        adps.sort(key=lambda x: x[1])
        team_queues[team] = [pid for pid, _ in adps]

    picks = []
    round_num = 1
    while True:
        order = get_round_order(round_num)
        any_picked = False
        for team in order:
            queue = team_queues.get(team, [])
            if queue:
                player_id = queue.pop(0)
                picks.append((team, player_id))
                any_picked = True
        if not any_picked:
            break
        round_num += 1

    return picks


def main():
    players_dict = load_master_players()
    picks = reconstruct_pick_order(players_dict)

    print(f"Reconstructed {len(picks)} picks\n")
    for i, (team, pid) in enumerate(picks, 1):
        name = pid
        for key, p in players_dict.items():
            if p.get("player_id") == pid:
                name = p.get("name", pid)
                break
        rnd = ((i - 1) // 13) + 1
        print(f"Pick {i:3d} (R{rnd}): {team:30s} -> {name}")

    print()
    resp = input("Submit these picks to the server? [y/N] ")
    if resp.strip().lower() != 'y':
        print("Aborted.")
        return

    for i, (team, pid) in enumerate(picks, 1):
        resp = requests.post(f"{BASE}/api/draft/pick", json={
            "player_id": pid,
            "team_name": team
        })
        data = resp.json()
        if data.get("success"):
            print(f"Pick {i}: ✓")
        else:
            print(f"Pick {i}: FAILED — {data.get('message')}")

    print(f"\nDone! {len(picks)} picks restored.")


if __name__ == "__main__":
    main()
