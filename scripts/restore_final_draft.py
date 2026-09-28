"""Restore the complete 23-round draft from CBS results."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import requests
import time

BASE = "http://localhost:5001"

TEAM_ORDER = [
    "Runtime Terror", "Dawg", "Long Balls", "Simba's Dublin Green Sox",
    "Young Guns", "Gashouse Gang", "Magnum GI", "Trex",
    "Like a Nightmare", "Big Sticks", "MAGA DOGE", "Guillotine", "Rieken Havoc"
]
FIXED_ROUNDS = 3

def get_round_order(round_num):
    """Return team order for a given round. Rounds 1-3 fixed, 4+ snake."""
    if round_num <= FIXED_ROUNDS:
        return TEAM_ORDER[:]
    snake_idx = round_num - FIXED_ROUNDS  # 1-based
    if snake_idx % 2 == 1:  # Odd snake rounds = reverse
        return list(reversed(TEAM_ORDER))
    return TEAM_ORDER[:]

# All 23 rounds — each list is in CBS draft position order (1-13)
# CBS positions map to TEAM_ORDER indices: 0=RT, 1=Dawg, ..., 12=Rieken Havoc
ROUNDS = {
    1: [
        "aaron_judge", "shohei_ohtani", "juan_soto", "bobby_witt",
        "elly_de_la_cruz", "tarik_skubal", "kyle_tucker", "ronald_acuna",
        "paul_skenes", "julio_rodriguez", "garrett_crochet", "gunnar_henderson",
        "jose_ramirez"
    ],
    2: [
        "corbin_carroll", "fernando_tatis", "nick_kurtz", "cal_raleigh",
        "kyle_schwarber", "jazz_chisholm", "vladimir_guerrero", "mookie_betts",
        "ketel_marte", "junior_caminero", "yoshinobu_yamamoto", "jackson_chourio",
        "francisco_lindor"
    ],
    3: [
        "pete_alonso", "james_wood", "cristopher_sanchez", "bryan_woo",
        "matt_olson", "willson_contreras", "trea_turner", "pete_crow_armstrong",
        "manny_machado", "hunter_brown", "rafael_devers", "logan_gilbert",
        "chris_sale"
    ],
    4: [
        "wyatt_langford", "zach_neto", "yordan_alvarez", "bryce_harper",
        "freddie_freeman", "logan_webb", "brent_rooker", "joe_ryan",
        "roman_anthony", "cole_ragans", "mason_miller", "max_fried",
        "jacob_degrom"
    ],
    5: [
        "brice_turang", "edwin_diaz", "eugenio_suarez", "josh_naylor",
        "austin_riley", "cade_smith", "andres_munoz", "george_kirby",
        "jackson_merrill", "jesus_luzardo", "hunter_goodman", "tyler_soderstrom",
        "jhoan_duran"
    ],
    6: [
        "cody_bellinger", "jarren_duran", "cj_abrams", "geraldo_perdomo",
        "byron_buxton", "framber_valdez", "tyler_glasnow", "bo_bichette",
        "riley_greene", "maikel_garcia", "freddy_peralta", "corey_seager",
        "aroldis_chapman"
    ],
    7: [
        "eury_perez", "randy_arozarena", "dylan_cease", "david_bednar",
        "ben_rice", "george_springer", "raisel_iglesias", "vinnie_pasquantino",
        "willy_adames", "oneil_cruz", "michael_harris", "devin_williams",
        "christian_yelich"
    ],
    8: [
        "kyle_bradish", "nolan_mclean", "ryan_helsley", "daniel_palencia",
        "shohei_ohtani_pitcher", "shea_langeliers", "sandy_alcantara", "brandon_nimmo",
        "nick_pivetta", "kyle_stowers", "chase_burns", "kevin_gausman",
        "michael_busch"
    ],
    9: [
        "griffin_jax", "seiya_suzuki", "luke_keaschall", "teoscar_hernandez",
        "zack_wheeler", "alex_bregman", "agustin_ramirez", "spencer_strider",
        "jacob_misiorowski", "salvador_perez", "jeff_hoffman", "nick_lodolo",
        "cameron_schlittler"
    ],
    10: [
        "luis_robert", "ryan_pepiot", "trevor_story", "josh_hader",
        "emmet_sheehan", "trevor_megill", "andy_pages", "colton_cowser",
        "brandon_woodruff", "will_smith", "jo_adell", "jose_altuve",
        "jakob_marsee"
    ],
    11: [
        "yandy_diaz", "jeremy_pena", "lawrence_butler", "emilio_pagan",
        "blake_snell", "drake_baldwin", "nathan_eovaldi", "jackson_holliday",
        "pete_fairbanks", "nico_hoerner", "michael_king", "jac_caglianone",
        "carlos_estevez"
    ],
    12: [
        "trevor_rogers", "drew_rasmussen", "trey_yesavage", "brandon_lowe",
        "ryan_walker", "matt_chapman", "kris_bubic", "christian_walker",
        "shane_mcclanahan", "daulton_varsho", "adley_rutschman", "munetaka_murakami",
        "taylor_ward"
    ],
    13: [
        "sonny_gray", "kenley_jansen", "sal_stewart", "spencer_torkelson",
        "luis_castillo", "brenton_doyle", "robbie_ray", "mike_trout",
        "steven_kwan", "mackenzie_gore", "gavin_williams", "noelvi_marte",
        "bubba_chandler"
    ],
    14: [
        "jonathan_aranda", "matt_mclain", "ozzie_albies", "ranger_suarez",
        "edward_cabrera", "konnor_griffin", "xavier_edwards", "matthew_boyd",
        "shota_imanaga", "ceddanne_rafaela", "jacob_wilson", "willson_contreras_2",
        "dennis_santana"
    ],
    15: [
        "dansby_swanson", "bryan_abreu", "jj_wetherholt", "tanner_bibee",
        "ian_happ", "willi_castro", "joshua_lowe", "seranthony_dominguez",
        "caleb_durbin", "robert_garcia", "chandler_simpson", "jose_caballero",
        "kazuma_okamoto"
    ],
    16: [
        "tatsuya_imai", "robert_suarez", "bryan_reynolds", "wilyer_abreu",
        "cade_horton", "ivan_herrera", "giancarlo_stanton", "kevin_mcgonigle",
        "gerrit_cole", "aaron_nola", "addison_barger", "carlos_rodon",
        "abner_uribe"
    ],
    17: [
        "yainer_diaz", "royce_lewis", "jack_leiter", "marcus_semien",
        "trent_grisham", "sean_manaea", "riley_obrien", "kirby_yates",
        "dylan_crews", "alec_burleson", "ramon_laureano", "max_muncy",
        "jorge_polanco"
    ],
    18: [
        "edwin_uceta", "connelly_early", "kyle_manzardo", "jack_flaherty",
        "sal_frelick", "shane_baz", "jake_burger", "casey_mize",
        "shane_bieber", "merrill_kelly", "zac_gallen", "alejandro_kirk",
        "colson_montgomery"
    ],
    19: [
        "andrew_abbott", "grant_taylor", "adolis_garcia", "kerry_carpenter",
        "gleyber_torres", "garrett_cleavinger", "max_muncy_2", "carlos_correa",
        "bryson_stott", "victor_scott", "dustin_may", "francisco_alvarez",
        "xander_bogaerts"
    ],
    20: [
        "daylen_lile", "justin_steele", "ryne_nelson", "yusei_kikuchi",
        "braxton_ashcraft", "ryan_weathers", "grant_holmes", "shane_smith",
        "isaac_paredes", "chad_patrick", "grayson_rodriguez", "joey_cantillo",
        "noah_cameron"
    ],
    21: [
        "alec_bohm", "jeremiah_estrada", "kodai_senga", "joe_musgrove",
        "otto_lopez", "jose_ferrer", "tyler_fitzgerald", "jasson_dominguez",
        "samuel_basallo", "mickey_moniak", "nolan_arenado", "heliot_ramos",
        "carter_jensen"
    ],
    22: [
        "hunter_greene", "will_vest", "justin_crawford", "mitch_keller",
        "bryce_miller", "nolan_gorman", "reynaldo_lopez", "chris_bassitt",
        "andrew_painter", "luis_garcia", "jordan_lawlar", "brendan_donovan",
        "matthew_liberatore"
    ],
    23: [
        "roki_sasaki", "andrew_vaughn", "kevin_ginkel", "dylan_moore",
        "payton_tolle", "brady_singer", "gabriel_moreno", "paul_sewald",
        "luis_severino", "taylor_rogers", "spencer_steer", "max_meyer",
        "quinn_mathews"
    ],
}


def build_picks():
    """Build the full pick list in correct draft order.
    
    Each round's player list is in CBS position order (index 0=RT, 1=Dawg, etc).
    We need to submit picks in the actual draft order for that round
    (which may be reversed for snake rounds).
    """
    picks = []
    for round_num in range(1, 24):
        order = get_round_order(round_num)  # Team order for this round
        for team in order:
            # Find this team's CBS position index
            cbs_idx = TEAM_ORDER.index(team)
            player_id = ROUNDS[round_num][cbs_idx]
            picks.append((team, player_id, round_num))
    return picks


def main():
    picks = build_picks()
    print(f"Total picks to submit: {len(picks)}")

    # Step 1: Restart the draft
    print("\nRestarting draft...")
    r = requests.post(f"{BASE}/api/draft/restart")
    if not r.ok:
        print(f"  WARN restart: {r.status_code} {r.text[:200]}")

    # Step 2: Create a fresh draft
    print("Creating fresh draft...")
    r = requests.post(f"{BASE}/api/draft/create", json={
        "draft_id": "draft_1773878841",
        "league_name": "Bob Uecker League",
        "total_teams": 13,
        "roster_size": 23,
        "my_team_name": "Runtime Terror"
    })
    if not r.ok:
        print(f"  FAIL create: {r.status_code} {r.text[:200]}")
        return
    print("  Draft created (roster_size=23)")

    # Step 3: Submit all 299 picks
    errors = []
    for i, (team, player_id, rnd) in enumerate(picks, 1):
        r = requests.post(f"{BASE}/api/draft/pick", json={
            "player_id": player_id,
            "team_name": team
        })
        if r.ok:
            if i % 26 == 0 or i == len(picks):
                print(f"  Pick {i}/299 R{rnd} {team} -> {player_id} ✓")
        else:
            msg = r.json().get('message', r.text[:100]) if r.headers.get('content-type','').startswith('application/json') else r.text[:100]
            errors.append((i, team, player_id, rnd, msg))
            print(f"  FAIL Pick {i}/299 R{rnd} {team} -> {player_id}: {msg}")

    # Step 4: Verify
    print(f"\n{'='*50}")
    r = requests.get(f"{BASE}/api/draft/current")
    d = r.json()["draft"]
    print(f"Final state: {len(d['picks'])} picks, round {d['current_round']}")
    
    if errors:
        print(f"\n{len(errors)} ERRORS:")
        for i, team, pid, rnd, msg in errors:
            print(f"  #{i} R{rnd} {team} -> {pid}: {msg}")
    else:
        print("All 299 picks submitted successfully!")

    # Show RT roster
    rt_players = d['team_rosters'].get('Runtime Terror', [])
    print(f"\nRuntime Terror roster ({len(rt_players)} players):")
    for pid in rt_players:
        print(f"  {pid}")


if __name__ == "__main__":
    main()
