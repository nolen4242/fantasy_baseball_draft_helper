"""Data loaders for various baseball data sources."""
import json
import csv
from pathlib import Path
from typing import List, Dict, Optional
from src.models.player import Player


class DataSourceLoader:
    """Base class for loading data from various sources."""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data" / "sources"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def normalize_player_name(self, name: str) -> str:
        """Normalize player name for matching."""
        # Remove common suffixes and normalize
        name = name.strip()
        # Remove team abbreviations in parentheses
        if '(' in name and ')' in name:
            name = name.split('(')[0].strip()
        return name.lower().replace('.', '').replace("'", "").replace("-", " ")


class BaseballReferenceLoader(DataSourceLoader):
    """Load data from Baseball Reference."""
    
    def load_standard_stats(self, year: int = 2024, player_type: str = "batters") -> Dict[str, Dict]:
        """Load standard counting stats from BBRef."""
        filepath = self.data_dir / "baseball_reference" / "standard_stats" / f"{player_type}_{year}.csv"
        if not filepath.exists():
            return {}
        
        stats = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = self.normalize_player_name(row.get('Name', ''))
                if not name:
                    continue
                
                stats[name] = {
                    'runs': self._safe_float(row.get('R')),
                    'rbi': self._safe_float(row.get('RBI')),
                    'home_runs': self._safe_float(row.get('HR')),
                    'stolen_bases': self._safe_float(row.get('SB')),
                    'hits': self._safe_float(row.get('H')),
                    'doubles': self._safe_float(row.get('2B')),
                    'triples': self._safe_float(row.get('3B')),
                    'walks': self._safe_float(row.get('BB')),
                    'strikeouts': self._safe_float(row.get('SO')),
                    'avg': self._safe_float(row.get('AVG')),
                    'slg': self._safe_float(row.get('SLG')),
                    'ops': self._safe_float(row.get('OPS')),
                    'wins': self._safe_float(row.get('W')),
                    'losses': self._safe_float(row.get('L')),
                    'saves': self._safe_float(row.get('SV')),
                    'innings_pitched': self._safe_float(row.get('IP')),
                    'earned_runs': self._safe_float(row.get('ER')),
                    'mvps': self._safe_int(row.get('MVPs')),
                    'all_stars': self._safe_int(row.get('AllStars')),
                    'gold_gloves': self._safe_int(row.get('GoldGloves')),
                    'cy_youngs': self._safe_int(row.get('CyYoungs')),
                }
        return stats
    
    def load_advanced_stats(self, year: int = 2024, player_type: str = "batters") -> Dict[str, Dict]:
        """Load advanced stats from BBRef."""
        filepath = self.data_dir / "baseball_reference" / "advanced_stats" / f"{player_type}_{year}.csv"
        if not filepath.exists():
            return {}
        
        stats = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = self.normalize_player_name(row.get('Name', ''))
                if not name:
                    continue
                
                stats[name] = {
                    'wrc_plus': self._safe_float(row.get('wRC+')),
                    'ops_plus': self._safe_float(row.get('OPS+')),
                    'era_plus': self._safe_float(row.get('ERA+')),
                    'fip': self._safe_float(row.get('FIP')),
                    'xfip': self._safe_float(row.get('xFIP')),
                    'war': self._safe_float(row.get('WAR')),
                }
        return stats
    
    def load_projections(self, year: int = 2025, player_type: str = "batters") -> Dict[str, Dict]:
        """Load BBRef projections."""
        filepath = self.data_dir / "baseball_reference" / "projections" / f"{player_type}_{year}.csv"
        if not filepath.exists():
            return {}
        
        proj = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = self.normalize_player_name(row.get('Name', ''))
                if not name:
                    continue
                
                proj[name] = {
                    'hr': self._safe_float(row.get('HR')),
                    'r': self._safe_float(row.get('R')),
                    'rbi': self._safe_float(row.get('RBI')),
                    'sb': self._safe_float(row.get('SB')),
                    'obp': self._safe_float(row.get('OBP')),
                    'w': self._safe_float(row.get('W')),
                    'k': self._safe_float(row.get('K')),
                    'era': self._safe_float(row.get('ERA')),
                    'whip': self._safe_float(row.get('WHIP')),
                }
        return proj
    
    def _safe_float(self, value: Optional[str]) -> Optional[float]:
        """Safely convert to float."""
        if not value or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_int(self, value: Optional[str]) -> Optional[int]:
        """Safely convert to int."""
        if not value or value == '':
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None


class BaseballSavantLoader(DataSourceLoader):
    """Load Statcast data from Baseball Savant."""
    
    def load_statcast(self, year: int = 2024, player_type: str = "batters") -> Dict[str, Dict]:
        """Load Statcast data."""
        filepath = self.data_dir / "baseball_savant" / "statcast" / f"{player_type}_{year}.csv"
        if not filepath.exists():
            return {}
        
        statcast = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = self.normalize_player_name(row.get('Name', ''))
                if not name:
                    continue
                
                statcast[name] = {
                    'exit_velocity': self._safe_float(row.get('Exit Velocity')),
                    'launch_angle': self._safe_float(row.get('Launch Angle')),
                    'barrel_rate': self._safe_float(row.get('Barrel %')),
                    'hard_hit_rate': self._safe_float(row.get('Hard Hit %')),
                    'xba': self._safe_float(row.get('xBA')),
                    'xslg': self._safe_float(row.get('xSLG')),
                    'xwoba': self._safe_float(row.get('xwOBA')),
                    'spin_rate': self._safe_float(row.get('Spin Rate')),
                    'velocity': self._safe_float(row.get('Velocity')),
                    'sprint_speed': self._safe_float(row.get('Sprint Speed')),
                    'defensive_runs': self._safe_float(row.get('Defensive Runs Saved')),
                }
        return statcast
    
    def load_park_factors(self, year: int = 2024) -> Dict[str, Dict]:
        """Load park factor data."""
        filepath = self.data_dir / "baseball_savant" / "park_factors" / f"park_factors_{year}.csv"
        if not filepath.exists():
            return {}
        
        park_factors = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                team = row.get('Team', '').strip().upper()
                if not team:
                    continue
                
                park_factors[team] = {
                    'offense': self._safe_float(row.get('Offense Factor')),
                    'pitching': self._safe_float(row.get('Pitching Factor')),
                    'hr': self._safe_float(row.get('HR Factor')),
                }
        return park_factors
    
    def _safe_float(self, value: Optional[str]) -> Optional[float]:
        """Safely convert to float."""
        if not value or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


class FangraphsLoader(DataSourceLoader):
    """Load projection data from Fangraphs."""
    
    def load_projections(self, system: str = "steamer", year: int = 2025, player_type: str = "batters") -> Dict[str, Dict]:
        """Load Fangraphs projections by system."""
        filepath = self.data_dir / "fangraphs" / "projections" / f"{system}_{player_type}_{year}.csv"
        if not filepath.exists():
            return {}
        
        proj = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = self.normalize_player_name(row.get('Name', ''))
                if not name:
                    continue
                
                proj[name] = {
                    'hr': self._safe_float(row.get('HR')),
                    'r': self._safe_float(row.get('R')),
                    'rbi': self._safe_float(row.get('RBI')),
                    'sb': self._safe_float(row.get('SB')),
                    'obp': self._safe_float(row.get('OBP')),
                    'w': self._safe_float(row.get('W')),
                    'k': self._safe_float(row.get('K')),
                    'era': self._safe_float(row.get('ERA')),
                    'whip': self._safe_float(row.get('WHIP')),
                }
        return proj
    
    def _safe_float(self, value: Optional[str]) -> Optional[float]:
        """Safely convert to float."""
        if not value or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


class RotowireLoader(DataSourceLoader):
    """Load news and injury data from Rotowire."""
    
    def load_news(self, year: int = 2025) -> Dict[str, Dict]:
        """Load player news and qualitative data."""
        filepath = self.data_dir / "rotowire" / "news" / f"player_news_{year}.json"
        if not filepath.exists():
            return {}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            news_data = json.load(f)
        
        news = {}
        for item in news_data:
            name = self.normalize_player_name(item.get('player_name', ''))
            if not name:
                continue
            
            if name not in news:
                news[name] = {
                    'items': [],
                    'sentiment': 0.0,
                    'contract_year': item.get('contract_year', False),
                    'big_contract': item.get('big_contract', False),
                    'prospect_called_up': item.get('prospect_called_up', False),
                }
            
            news[name]['items'].append(item.get('news_text', ''))
            # Aggregate sentiment
            sentiment = item.get('sentiment', 0.0)
            news[name]['sentiment'] = (news[name]['sentiment'] + sentiment) / 2
        
        return news
    
    def load_injuries(self) -> Dict[str, Dict]:
        """Load injury history and risk data."""
        # Historical injuries
        hist_file = self.data_dir / "rotowire" / "injuries" / "injury_history.csv"
        current_file = self.data_dir / "rotowire" / "injuries" / "current_injuries.json"
        
        injuries = {}
        
        # Load historical
        if hist_file.exists():
            with open(hist_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = self.normalize_player_name(row.get('Name', ''))
                    if not name:
                        continue
                    
                    if name not in injuries:
                        injuries[name] = {
                            'history': [],
                            'risk_score': 0.0,
                            'current_injury': None,
                        }
                    
                    injury = row.get('Injury', '')
                    if injury:
                        injuries[name]['history'].append(injury)
                    
                    # Calculate risk score (0-1) based on frequency and severity
                    risk = self._safe_float(row.get('Risk Score', '0'))
                    if risk:
                        injuries[name]['risk_score'] = max(injuries[name]['risk_score'], risk)
        
        # Load current injuries
        if current_file.exists():
            with open(current_file, 'r', encoding='utf-8') as f:
                current_data = json.load(f)
            
            for item in current_data:
                name = self.normalize_player_name(item.get('player_name', ''))
                if name in injuries:
                    injuries[name]['current_injury'] = item.get('injury_status', None)
        
        return injuries


class NFBCLoader(DataSourceLoader):
    """Load ADP and draft history from NFBC."""
    
    def load_adp(self, year: int = 2025) -> Dict[str, Dict]:
        """Load NFBC professional ADP data."""
        filepath = self.data_dir / "nfbc" / "adp" / f"nfbc_adp_{year}.csv"
        if not filepath.exists():
            return {}
        
        adp_data = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = self.normalize_player_name(row.get('Player Name', ''))
                if not name:
                    continue
                
                adp_data[name] = {
                    'adp': self._safe_float(row.get('ADP')),
                    'std_dev': self._safe_float(row.get('Std Dev')),
                    'min': self._safe_float(row.get('Min')),
                    'max': self._safe_float(row.get('Max')),
                }
        return adp_data
    
    def load_draft_history(self, year: int = 2024) -> List[Dict]:
        """Load historical NFBC draft results."""
        filepath = self.data_dir / "nfbc" / "draft_history" / f"nfbc_drafts_{year}.json"
        if not filepath.exists():
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _safe_float(self, value: Optional[str]) -> Optional[float]:
        """Safely convert to float."""
        if not value or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


class CBSLoader(DataSourceLoader):
    """Load position eligibility and historical draft data from CBS."""
    
    def load_position_eligibility(self, year: int = 2025) -> Dict[str, List[str]]:
        """Load position eligibility data."""
        filepath = self.data_dir / "cbs" / "position_eligibility" / f"positions_{year}.csv"
        if not filepath.exists():
            return {}
        
        eligibility = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = self.normalize_player_name(row.get('Name', ''))
                if not name:
                    continue
                
                positions_str = row.get('Positions', '')
                positions = [p.strip() for p in positions_str.split(',') if p.strip()]
                eligibility[name] = positions
        
        return eligibility
    
    def load_historical_drafts(self, year: int = 2024) -> List[Dict]:
        """Load historical CBS draft data."""
        filepath = self.data_dir / "cbs" / "historical_drafts" / f"cbs_drafts_{year}.json"
        if not filepath.exists():
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_league_thresholds(self, year: int = 2024) -> Dict[str, float]:
        """Load stats needed to win each category."""
        filepath = self.data_dir / "cbs" / "league_thresholds" / f"winning_thresholds_{year}.json"
        if not filepath.exists():
            return {}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


class BBForecasterLoader(DataSourceLoader):
    """Load prediction market data from BB Forecaster."""
    
    def load_predictions(self, year: int = 2025) -> Dict[str, float]:
        """Load BB Forecaster prediction market data."""
        filepath = self.data_dir / "bb_forecaster" / f"predictions_{year}.csv"
        if not filepath.exists():
            return {}
        
        predictions = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = self.normalize_player_name(row.get('Name', ''))
                if not name:
                    continue
                
                pred = self._safe_float(row.get('Prediction Value'))
                if pred:
                    predictions[name] = pred
        
        return predictions
    
    def _safe_float(self, value: Optional[str]) -> Optional[float]:
        """Safely convert to float."""
        if not value or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

