"""Restore draft v2 — correct team order and updated rosters (75 picks)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import requests

BASE = "http://localhost:5001"

TEAM_ORDER = [
    "Runtime Terror", "Dawg", "Long Balls", "Simba's Dublin Green Sox",
    "Young Guns", "Gashouse Gang", "Magnum GI", "Trex",
    "Like a Nightmare", "Big Sticks", "MAGA DOGE", "Guillotine", "Rieken Havoc"
]
FIXED_ROUNDS = 3

TEAM_PICKS = {
    "Big Sticks": [
        "bryce_harper", "junior_caminero", "geraldo_perdomo",
        "julio_rodriguez", "jesus_luzardo", "hunter_brown"
    ],
    "Dawg": [
        "fernando_tatis", "james_wood", "shohei_ohtani",
        "edwin_diaz", "max_fried"
    ],
    "Gashouse Gang": [
        "willson_contreras", "jazz_chisholm", "bo_bichette",
        "cade_smith", "joe_ryan", "tarik_skubal"
    ],
    "Guillotine": [
        "tyler_soderstrom", "gunnar_henderson", "zach_neto",
        "jarren_duran", "jackson_chourio", "logan_gilbert"
    ],
    "Like a Nightmare": [
        "freddie_freeman", "ketel_marte", "manny_machado",
        "byron_buxton", "jackson_merrill", "paul_skenes"
    ],
    "Long Balls": [
        "nick_kurtz", "eugenio_suarez", "juan_soto",
        "cristopher_sanchez", "mason_miller"
    ],
    "MAGA DOGE": [
        "hunter_goodman", "rafael_devers", "cj_abrams",
        "yordan_alvarez", "yoshinobu_yamamoto", "garrett_crochet"
    ],
    "Magnum GI": [
        "vladimir_guerrero", "trea_turner", "brent_rooker",
        "kyle_tucker", "tyler_glasnow", "andres_munoz"
    ],
    "Rieken Havoc": [
        "jose_ramirez", "francisco_lindor", "cody_bellinger",
        "wyatt_langford", "jhoan_duran", "chris_sale"
    ],
    "Runtime Terror": [
        "pete_alonso", "brice_turang", "corbin_carroll",
        "aaron_judge", "jacob_degrom"
    ],
    "Simba's Dublin Green Sox": [
        "cal_raleigh", "josh_naylor", "maikel_garcia",
        "bobby_witt", "bryan_woo", "cole_ragans"
    ],
    "Trex": [
        "mookie_betts", "pete_crow_armstrong", "ronald_acuna",
        "george_kirby", "logan_webb", "framber_valdez"
    ],
    "Young Guns": [
        "matt_olson", "austin_riley", "elly_de_la_cruz",
        "riley_greene", "roman_anthony", "kyle_schwarber"
    ],
}


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

    # First restart the draft to clear it
    print("\nClearing current draft...")
    resp = requests.post(f"{BASE}/api/draft/restart")
    data = resp.json()
    print(f"Restart: {data.get('message', 'done')}")

    # Submit each pick
    print("\nSubmitting picks...")
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
