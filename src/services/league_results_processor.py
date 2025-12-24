"""League results processor - analyzes historical league results for category thresholds."""
import csv
import json
from pathlib import Path
from typing import List, Dict
from collections import defaultdict
from statistics import median, mean


class LeagueResultsProcessor:
    """
    Processes historical league results to extract:
    - Category thresholds (what it takes to win)
    - Optimal category balance
    - Year-over-year trends
    - Winning team patterns
    """
    
    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        self.raw_dir = project_root / "raw" / "historical_data"
        self.output_dir = project_root / "data" / "league_analysis" / "category_thresholds"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.historical_years = [2021, 2022, 2023, 2024, 2025]
        
        # Bob Uecker League categories
        self.batting_categories = ['HR', 'OBP', 'R', 'RBI', 'SB']
        self.pitching_categories = ['ERA', 'K', 'S', 'WHIP', 'WQS']
        self.all_categories = self.batting_categories + self.pitching_categories
    
    def process_all_results(self) -> Dict:
        """
        Process all historical league results and generate analysis.
        """
        print("=" * 60)
        print("Processing League Results")
        print("=" * 60)
        
        all_results = []
        
        # Load all result files
        for year in self.historical_years:
            results_file = self.raw_dir / f"cbs_{year}_league_results.csv"
            if results_file.exists():
                print(f"\nProcessing {year} results...")
                year_results = self._load_results_file(results_file, year)
                all_results.append(year_results)
                print(f"  Loaded {len(year_results['teams'])} teams")
        
        # Generate analysis
        print("\n" + "=" * 60)
        print("Generating Category Analysis")
        print("=" * 60)
        
        category_thresholds = self._calculate_category_thresholds(all_results)
        optimal_balance = self._analyze_optimal_balance(all_results)
        trends = self._analyze_trends(all_results)
        
        # Save outputs
        self._save_winners(all_results)
        self._save_category_thresholds(category_thresholds)
        self._save_optimal_balance(optimal_balance)
        self._save_trends(trends)
        
        print(f"\n✅ League results processing complete!")
        print(f"   Processed {len(all_results)} years")
        print(f"   Total teams analyzed: {sum(len(r['teams']) for r in all_results)}")
        
        return {
            'years_processed': len(all_results),
            'total_teams': sum(len(r['teams']) for r in all_results),
            'years': [r['year'] for r in all_results]
        }
    
    def _load_results_file(self, filepath: Path, year: int) -> Dict:
        """Load and parse a league results file."""
        teams = []
        current_section = None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                i += 1
                continue
            
            # Check for overall standings
            if 'Rank' in line and 'Team' in line and 'Total' in line:
                i += 1
                # Parse overall standings
                while i < len(lines):
                    line = lines[i].strip()
                    if not line or line.startswith('Batting') or line.startswith('Pitching'):
                        break
                    
                    parts = [p.strip() for p in line.split(',') if p.strip()]
                    if len(parts) >= 4 and parts[0].isdigit():
                        try:
                            rank = int(parts[0])
                            team = parts[1]
                            batting_points = float(parts[2]) if parts[2] else 0.0
                            pitching_points = float(parts[3]) if len(parts) > 3 and parts[3] else 0.0
                            total_points = float(parts[4]) if len(parts) > 4 and parts[4] else batting_points + pitching_points
                            
                            teams.append({
                                'rank': rank,
                                'team': team,
                                'batting_points': batting_points,
                                'pitching_points': pitching_points,
                                'total_points': total_points,
                                'categories': {}
                            })
                        except (ValueError, IndexError):
                            pass
                    i += 1
                continue
            
            # Check for category breakdown
            if 'Breakdown' in line:
                current_section = None
                i += 1
                continue
            
            # Check for category header (Team,HR,Pts,Dif or Team,ERA,Pts,Dif)
            if line.startswith('Team,') and any(cat in line for cat in self.all_categories):
                # Determine category
                category = None
                for cat in self.all_categories:
                    if f',{cat},' in line or line.startswith(f'Team,{cat},'):
                        category = cat
                        break
                
                if category:
                    current_section = category
                    i += 1
                    # Parse category data
                    while i < len(lines):
                        line = lines[i].strip()
                        if not line or line.startswith('Team,') or 'Breakdown' in line:
                            break
                        
                        parts = [p.strip() for p in line.split(',') if p.strip()]
                        if len(parts) >= 2 and not parts[0].isdigit():
                            team = parts[0]
                            value_str = parts[1]
                            points = float(parts[2]) if len(parts) > 2 and parts[2] else 0.0
                            
                            # Find team and add category data
                            for team_data in teams:
                                if team_data['team'] == team:
                                    # Parse value (could be number or decimal)
                                    try:
                                        if category in ['ERA', 'WHIP', 'OBP']:
                                            value = float(value_str)
                                        else:
                                            value = float(value_str) if '.' not in value_str or value_str.replace('.', '').isdigit() else float(value_str)
                                        
                                        team_data['categories'][category] = {
                                            'value': value,
                                            'points': points,
                                            'rank': None  # Will calculate later
                                        }
                                    except (ValueError):
                                        pass
                                    break
                        i += 1
                    continue
            
            i += 1
        
        # Calculate category ranks
        for category in self.all_categories:
            category_values = []
            for team in teams:
                if category in team['categories']:
                    category_values.append((team['team'], team['categories'][category]['value']))
            
            # Sort by value (higher is better for most, lower for ERA/WHIP)
            if category in ['ERA', 'WHIP']:
                category_values.sort(key=lambda x: x[1])  # Lower is better
            else:
                category_values.sort(key=lambda x: x[1], reverse=True)  # Higher is better
            
            # Assign ranks
            for rank, (team_name, _) in enumerate(category_values, 1):
                for team in teams:
                    if team['team'] == team_name and category in team['categories']:
                        team['categories'][category]['rank'] = rank
                        break
        
        return {
            'year': year,
            'teams': teams,
            'winner': teams[0] if teams else None
        }
    
    def _calculate_category_thresholds(self, all_results: List[Dict]) -> Dict:
        """Calculate what it takes to win each category."""
        print("\nCalculating category thresholds...")
        
        thresholds = {}
        
        for category in self.all_categories:
            # Collect all values for this category
            all_values = []
            winning_values = []
            competitive_values = []  # Top 3 teams
            
            for year_result in all_results:
                for team in year_result['teams']:
                    if category in team['categories']:
                        value = team['categories'][category]['value']
                        all_values.append(value)
                        
                        if team['rank'] == 1:
                            winning_values.append(value)
                        elif team['rank'] <= 3:
                            competitive_values.append(value)
            
            if all_values:
                # For ERA/WHIP: lower is better, so sort ascending
                # For others: higher is better, so sort descending
                reverse_sort = category not in ['ERA', 'WHIP']
                sorted_values = sorted(all_values, reverse=reverse_sort)
                
                # Percentiles: for higher-is-better, p90 is high value (good)
                # For lower-is-better, p90 is low value (good)
                if reverse_sort:
                    # Higher is better: to_win should be high (p90), to_compete should be medium-high (p70)
                    to_win_idx = int(len(sorted_values) * 0.10)  # Top 10% = high value
                    to_compete_idx = int(len(sorted_values) * 0.30)  # Top 30% = competitive
                else:
                    # Lower is better: to_win should be low (p10), to_compete should be medium-low (p30)
                    to_win_idx = int(len(sorted_values) * 0.10)  # Bottom 10% = low value (good)
                    to_compete_idx = int(len(sorted_values) * 0.30)  # Bottom 30% = competitive
                
                thresholds[category] = {
                    'to_win': sorted_values[to_win_idx] if sorted_values else 0,
                    'to_compete': sorted_values[to_compete_idx] if sorted_values else 0,
                    'average': mean(all_values) if all_values else 0,
                    'median': median(all_values) if all_values else 0,
                    'percentiles': {
                        'p10': sorted_values[int(len(sorted_values) * 0.10)] if sorted_values else 0,
                        'p25': sorted_values[int(len(sorted_values) * 0.25)] if sorted_values else 0,
                        'p50': sorted_values[int(len(sorted_values) * 0.50)] if sorted_values else 0,
                        'p75': sorted_values[int(len(sorted_values) * 0.75)] if sorted_values else 0,
                        'p90': sorted_values[int(len(sorted_values) * 0.90)] if sorted_values else 0,
                        'p95': sorted_values[int(len(sorted_values) * 0.95)] if sorted_values else 0
                    },
                    'winning_teams_average': mean(winning_values) if winning_values else 0,
                    'competitive_teams_average': mean(competitive_values) if competitive_values else 0
                }
        
        return thresholds
    
    def _analyze_optimal_balance(self, all_results: List[Dict]) -> Dict:
        """Analyze optimal category balance for winning teams."""
        print("Analyzing optimal balance...")
        
        winning_teams = []
        for year_result in all_results:
            if year_result['winner']:
                winning_teams.append(year_result['winner'])
        
        # Calculate average category points for winners
        category_averages = defaultdict(list)
        for winner in winning_teams:
            for category in self.all_categories:
                if category in winner['categories']:
                    category_averages[category].append(winner['categories'][category]['points'])
        
        category_priorities = {}
        for category, points_list in category_averages.items():
            avg_points = mean(points_list) if points_list else 0
            category_priorities[category] = avg_points
        
        # Categorize by priority
        sorted_categories = sorted(category_priorities.items(), key=lambda x: x[1], reverse=True)
        
        high_priority = [cat for cat, pts in sorted_categories if pts >= 12]
        medium_priority = [cat for cat, pts in sorted_categories if 8 <= pts < 12]
        low_priority = [cat for cat, pts in sorted_categories if pts < 8]
        
        return {
            'category_priorities': category_priorities,
            'high_priority': high_priority,
            'medium_priority': medium_priority,
            'low_priority': low_priority,
            'description': f"Winning teams average {mean([w['total_points'] for w in winning_teams]):.1f} total points",
            'winning_teams_count': len(winning_teams)
        }
    
    def _analyze_trends(self, all_results: List[Dict]) -> Dict:
        """Analyze year-over-year trends."""
        print("Analyzing trends...")
        
        trends = {}
        
        for category in self.all_categories:
            year_values = defaultdict(list)
            
            for year_result in all_results:
                for team in year_result['teams']:
                    if category in team['categories']:
                        year_values[year_result['year']].append(team['categories'][category]['value'])
            
            # Calculate average per year
            yearly_averages = {}
            for year, values in year_values.items():
                yearly_averages[year] = mean(values) if values else 0
            
            trends[category] = {
                'yearly_averages': yearly_averages,
                'trend': self._calculate_trend(yearly_averages)
            }
        
        return trends
    
    def _calculate_trend(self, yearly_averages: Dict[int, float]) -> str:
        """Calculate if category is trending up or down."""
        if len(yearly_averages) < 2:
            return "insufficient_data"
        
        sorted_years = sorted(yearly_averages.keys())
        first_avg = yearly_averages[sorted_years[0]]
        last_avg = yearly_averages[sorted_years[-1]]
        
        if last_avg > first_avg * 1.05:
            return "increasing"
        elif last_avg < first_avg * 0.95:
            return "decreasing"
        else:
            return "stable"
    
    def _save_winners(self, all_results: List[Dict]):
        """Save all winning teams."""
        output_file = self.output_dir / "winners.json"
        
        winners_data = {
            'winners': [r['winner'] for r in all_results if r.get('winner')],
            'all_teams': all_results,
            'metadata': {
                'years': [r['year'] for r in all_results],
                'total_teams': sum(len(r['teams']) for r in all_results)
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(winners_data, f, indent=2)
        print(f"✅ Saved winners: {output_file}")
    
    def _save_category_thresholds(self, thresholds: Dict):
        """Save category thresholds."""
        output_file = self.output_dir / "category_thresholds.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(thresholds, f, indent=2)
        print(f"✅ Saved category thresholds: {output_file}")
    
    def _save_optimal_balance(self, optimal_balance: Dict):
        """Save optimal balance analysis."""
        output_file = self.output_dir / "optimal_balance.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(optimal_balance, f, indent=2)
        print(f"✅ Saved optimal balance: {output_file}")
    
    def _save_trends(self, trends: Dict):
        """Save trends analysis."""
        output_file = self.output_dir / "trends.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(trends, f, indent=2)
        print(f"✅ Saved trends: {output_file}")

