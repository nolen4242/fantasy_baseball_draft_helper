"""
Build player database from source files.

Pipeline order:
  1. CBS player list (foundation - who's draftable)
  2. NFBC ADP
  3. Projection systems (Steamer, ATC, Depth Charts) - blended consensus
  4. Savant historical (future)

Usage:
  python3 -m scripts.build_player_db
"""
import csv
import json
import re
import unicodedata
from pathlib import Path

DATA_DIR = Path("data")
SOURCES_DIR = DATA_DIR / "sources"

# Known positions for parsing CBS player strings
POSITIONS = {
    'P', 'SP', 'RP', 'C', '1B', '2B', '3B', 'SS', 'OF',
    'DH', 'RF', 'LF', 'CF', 'MI', 'CI', 'U', 'UT',
}


# CBS name -> FanGraphs name (normalized forms)
NAME_ALIASES = {
    'zachary neto': 'zach neto',
    'cameron schlittler': 'cam schlittler',
    'jose ferrer': 'jose a ferrer',
    'josh h smith': 'josh smith',
    'hye seong kim': 'hyeseong kim',
    'logan taylor allen': 'logan allen',
    'joshua lowe': 'josh lowe',
    'jaison chourio': 'jackson chourio',
}


def normalize_name(name: str) -> str:
    """Normalize player name for matching."""
    n = unicodedata.normalize('NFD', name)
    n = ''.join(c for c in n if unicodedata.category(c) != 'Mn')
    n = n.lower().strip()
    n = re.sub(r'\s+(jr\.?|sr\.?|ii|iii|iv|v|2nd|3rd|4th)$', '', n)
    n = n.replace(".", "").replace("'", "").replace("-", " ")
    n = re.sub(r'\s+', ' ', n).strip()
    return NAME_ALIASES.get(n, n)


def parse_cbs_player_string(raw: str):
    """Parse 'Aaron Judge RF  NYY' into (name, position, team)."""
    tokens = raw.split()
    name_parts = []
    position = ''
    team = ''
    for i, t in enumerate(tokens):
        if t.upper() in POSITIONS:
            position = t.upper()
            remaining = tokens[i + 1:]
            team = remaining[-1].upper() if remaining else ''
            break
        name_parts.append(t)
    name = ' '.join(name_parts)
    return name, position, team


def step1_cbs_foundation() -> dict:
    """Step 1: Build master dict from CBS player list."""
    cbs_file = SOURCES_DIR / "cbs" / "cbs-players.csv"
    if not cbs_file.exists():
        print("ERROR: CBS player file not found")
        return {}

    master = {}
    with open(cbs_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = row.get('Player', '').strip()
            if not raw:
                continue
            name, position, team = parse_cbs_player_string(raw)
            if not name:
                continue

            norm = normalize_name(name)
            player_id = norm.replace(' ', '_')

            cbs_adp = None
            try:
                cbs_adp = float(row.get('Avg Pos', '').strip())
            except (ValueError, TypeError):
                pass

            master[norm] = {
                'name': name,
                'normalized_name': norm,
                'player_id': player_id,
                'position': position,
                'team': team,
                'cbs_rank': row.get('Rank', '').strip(),
                'cbs_adp': cbs_adp,
                'nfbc_adp': None,
                'projections': {},
            }

    print(f"Step 1 - CBS foundation: {len(master)} players")
    return master


def step2_nfbc_adp(master: dict) -> dict:
    """Step 2: Merge NFBC ADP data."""
    adp_file = SOURCES_DIR / "nfbc" / "adp.tsv"
    if not adp_file.exists():
        print("Step 2 - NFBC ADP: file not found, skipping")
        return master

    matched = 0
    with open(adp_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            name_raw = row.get('Player', '').strip()
            adp_str = row.get('ADP', '').strip()
            if not name_raw or not adp_str:
                continue
            # Convert "Last, First" to "First Last"
            if ',' in name_raw:
                parts = name_raw.split(',', 1)
                name = f'{parts[1].strip()} {parts[0].strip()}'
            else:
                name = name_raw
            try:
                adp = float(adp_str)
            except (ValueError, TypeError):
                continue
            norm = normalize_name(name)
            if norm in master:
                master[norm]['nfbc_adp'] = adp
                matched += 1

    print(f"Step 2 - NFBC ADP: {matched} matched")
    return master


def step3_projections(master: dict) -> dict:
    """Step 3: Merge projection systems (Steamer, ATC, Depth Charts)."""
    proj_dir = SOURCES_DIR / "projections"
    if not proj_dir.exists():
        print("Step 3 - Projections: directory not found, skipping")
        return master

    # Batter stat keys from FanGraphs CSV columns
    batter_stats = {
        'hr': 'projected_home_runs',
        'obp': 'projected_obp',
        'r': 'projected_runs',
        'rbi': 'projected_rbi',
        'sb': 'projected_stolen_bases',
    }

    # Pitcher stat keys
    pitcher_stats = {
        'w': 'projected_wins',
        'sv': 'projected_saves',
        'ip': 'projected_innings_pitched',
        'era': 'projected_era',
        'k/9': 'k_per_9',  # We'll derive total K from K/9 and IP
        'bb/9': 'bb_per_9',
        'hr/9': 'hr_per_9',
        'gs': 'games_started',
        'g': 'games',
    }

    projection_files = {
        'steamer': {
            'batters': 'steamer-batters.csv',
            'pitchers': 'steamer-pitchers.csv',
        },
        'atc': {
            'batters': 'atc-batters.csv',
            'pitchers': 'atc-pitchers.csv',
        },
        'depthcharts': {
            'batters': 'depthcharts-batters.csv',
            'pitchers': 'depthcharts-pitchers.csv',
        },
    }

    for source_name, files in projection_files.items():
        for player_type, filename in files.items():
            filepath = proj_dir / filename
            if not filepath.exists():
                print(f"  {source_name} {player_type}: not found, skipping")
                continue

            stat_map = batter_stats if player_type == 'batters' else pitcher_stats
            matched = 0

            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    norm_row = {k.lower().strip(): v for k, v in row.items()}
                    name = norm_row.get('name', '').strip()
                    if not name:
                        continue
                    norm = normalize_name(name)
                    if norm not in master:
                        continue

                    proj = {}
                    for csv_col, stat_key in stat_map.items():
                        val = norm_row.get(csv_col, '').strip()
                        if val:
                            try:
                                proj[stat_key] = float(val.replace('%', ''))
                            except (ValueError, TypeError):
                                pass

                    # Derive pitcher stats
                    if player_type == 'pitchers':
                        ip = proj.get('projected_innings_pitched', 0)
                        k9 = proj.get('k_per_9', 0)
                        gs = proj.get('games_started', 0)
                        if k9 and ip:
                            proj['projected_strikeouts'] = (k9 * ip) / 9.0
                        if gs:
                            proj['projected_quality_starts'] = gs * 0.65
                        bb9 = proj.get('bb_per_9', 0)
                        if bb9 and ip:
                            proj['projected_whip'] = (bb9 + 8.5) / 9.0
                        proj['projected_holds'] = None
                        # Determine position from stats if CBS has generic 'P'
                        if not master[norm].get('position') or master[norm]['position'] in ('P',):
                            saves = proj.get('projected_saves', 0)
                            if saves and saves > 5:
                                master[norm]['position'] = 'RP'
                            elif gs and gs > 5:
                                master[norm]['position'] = 'SP'

                    # Store under source_name:player_type so batter/pitcher
                    # projections don't overwrite each other (e.g. Ohtani)
                    key = f"{source_name}:{player_type}"
                    master[norm]['projections'][key] = proj
                    matched += 1

            print(f"  {source_name} {player_type}: {matched} matched")

    print(f"Step 3 - Projections merged")
    return master


def step4_savant_historical(master: dict) -> dict:
    """Step 4: Merge Baseball Savant historical data (2021-2025)."""
    savant_dir = SOURCES_DIR / "savant"
    if not savant_dir.exists():
        print("Step 4 - Savant: directory not found, skipping")
        return master

    # Batter stats we care about from Savant
    batter_stat_map = {
        'pa': 'pa', 'ab': 'ab', 'hit': 'h', 'home_run': 'hr',
        'r_run': 'r', 'b_rbi': 'rbi', 'r_total_stolen_base': 'sb',
        'strikeout': 'k', 'walk': 'bb',
        'batting_avg': 'avg', 'on_base_percent': 'obp', 'slg_percent': 'slg',
        'on_base_plus_slg': 'ops', 'isolated_power': 'iso', 'babip': 'babip',
        'xba': 'xba', 'xobp': 'xobp', 'xslg': 'xslg', 'xwoba': 'xwoba',
        'exit_velocity_avg': 'exit_velo', 'launch_angle_avg': 'launch_angle',
        'barrel_batted_rate': 'barrel_rate', 'hard_hit_percent': 'hard_hit_pct',
        'sweet_spot_percent': 'sweet_spot_pct',
        'avg_best_speed': 'sprint_speed',
        'k_percent': 'k_pct', 'bb_percent': 'bb_pct',
        'whiff_percent': 'whiff_pct', 'groundballs_percent': 'gb_pct',
        'flyballs_percent': 'fb_pct',
    }

    # Pitcher stats we care about from Savant
    pitcher_stat_map = {
        'p_game': 'g', 'p_formatted_ip': 'ip',
        'p_win': 'w', 'p_loss': 'l', 'p_save': 'sv', 'p_hold': 'hld',
        'p_starting_p': 'gs', 'p_quality_start': 'qs',
        'strikeout': 'k', 'walk': 'bb', 'hit': 'h', 'home_run': 'hr',
        'p_earned_run': 'er', 'p_era': 'era',
        'k_percent': 'k_pct', 'bb_percent': 'bb_pct',
        'xba': 'xba', 'xobp': 'xobp', 'xslg': 'xslg', 'xwoba': 'xwoba',
        'xwobacon': 'xwobacon',
        'exit_velocity_avg': 'exit_velo', 'launch_angle_avg': 'launch_angle',
        'barrel_batted_rate': 'barrel_rate',
        'whiff_percent': 'whiff_pct',
        'oz_swing_miss_percent': 'chase_miss_pct',
        'groundballs_percent': 'gb_pct', 'flyballs_percent': 'fb_pct',
    }

    years = ['2021', '2022', '2023', '2024', '2025']

    for player_type in ['batters', 'pitchers']:
        stat_map = batter_stat_map if player_type == 'batters' else pitcher_stat_map
        prefix = 'savant' if player_type == 'batters' else 'savant-pitchers'

        for year in years:
            if player_type == 'batters':
                filename = f'savant-{year}-batters.csv'
            else:
                filename = f'savant-pitchers-{year}.csv'
            filepath = savant_dir / filename
            if not filepath.exists():
                continue

            matched = 0
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                # Savant CSVs have a quoted header "last_name, first_name" that
                # csv.DictReader splits on the internal comma. Read raw header
                # and fix it.
                raw_header = f.readline()
                # Replace the problematic quoted column name
                raw_header = raw_header.replace('"last_name, first_name"', 'player_name')
                raw_header = raw_header.strip()
                fieldnames = [h.strip().strip('"') for h in raw_header.split(',')]
                reader = csv.DictReader(f, fieldnames=fieldnames)
                for row in reader:
                    name_raw = row.get('player_name', '').strip().strip('"')
                    if not name_raw:
                        continue
                    if ',' in name_raw:
                        parts = name_raw.split(',', 1)
                        name = f'{parts[1].strip()} {parts[0].strip()}'
                    else:
                        name = name_raw

                    norm = normalize_name(name)
                    if norm not in master:
                        continue

                    # Parse stats
                    season = {}
                    for savant_col, our_key in stat_map.items():
                        val = row.get(savant_col, '').strip()
                        if val and val != '' and val != 'null':
                            try:
                                season[our_key] = float(val.replace('%', ''))
                            except (ValueError, TypeError):
                                pass

                    if not season:
                        continue

                    # Store under savant_history
                    if 'savant_history' not in master[norm]:
                        master[norm]['savant_history'] = {}
                    if player_type not in master[norm]['savant_history']:
                        master[norm]['savant_history'][player_type] = {}
                    master[norm]['savant_history'][player_type][year] = season
                    matched += 1

            print(f"  {player_type} {year}: {matched} matched")

    # Count totals
    has_savant = sum(1 for v in master.values() if v.get('savant_history'))
    print(f"Step 4 - Savant historical: {has_savant} players with history")
    return master


def blend_projections(master: dict) -> dict:
    """Blend all projection sources into consensus values on each player.
    
    Uses CBS position to determine whether to blend batter or pitcher projections.
    Keys in projections dict are 'source:batters' or 'source:pitchers'.
    """
    batter_keys = [
        'projected_home_runs', 'projected_obp', 'projected_runs',
        'projected_rbi', 'projected_stolen_bases',
    ]
    pitcher_keys = [
        'projected_wins', 'projected_quality_starts', 'projected_strikeouts',
        'projected_era', 'projected_whip', 'projected_saves',
        'projected_holds', 'projected_innings_pitched',
    ]

    for norm, pdata in master.items():
        projs = pdata.get('projections', {})
        if not projs:
            continue

        pos = pdata.get('position', '')
        is_pitcher = pos in ('SP', 'RP', 'P')
        target_type = 'pitchers' if is_pitcher else 'batters'
        stat_keys = pitcher_keys if is_pitcher else batter_keys

        # Filter to only the matching player type projections
        matching = {k: v for k, v in projs.items() if k.endswith(f':{target_type}')}
        if not matching:
            continue

        blended = {}
        for key in stat_keys:
            vals = []
            for source_data in matching.values():
                v = source_data.get(key)
                if v is not None:
                    vals.append(v)
            blended[key] = round(sum(vals) / len(vals), 4) if vals else None

        pdata['blended'] = blended

    return master


def save_master(master: dict):
    """Save master database as JSON."""
    output = DATA_DIR / "master_players.json"
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(master, f, indent=2)
    print(f"\nSaved {len(master)} players to {output}")

    # Also save summary stats
    has_nfbc = sum(1 for v in master.values() if v.get('nfbc_adp'))
    has_projs = sum(1 for v in master.values() if v.get('projections'))
    has_blend = sum(1 for v in master.values() if v.get('blended'))
    sources = set()
    for v in master.values():
        sources.update(v.get('projections', {}).keys())

    print(f"\n=== DATABASE SUMMARY ===")
    print(f"Total players: {len(master)}")
    print(f"With NFBC ADP: {has_nfbc}")
    print(f"With projections: {has_projs}")
    print(f"With blended consensus: {has_blend}")
    print(f"Projection sources: {', '.join(sorted(sources))}")
    has_savant = sum(1 for v in master.values() if v.get('savant_history'))
    print(f"With Savant history: {has_savant}")


def main():
    print("=== Building Player Database ===\n")
    master = step1_cbs_foundation()
    master = step2_nfbc_adp(master)
    master = step3_projections(master)
    master = step4_savant_historical(master)
    master = blend_projections(master)
    save_master(master)


if __name__ == '__main__':
    main()
