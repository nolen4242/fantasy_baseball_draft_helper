"""
Projection weighting configuration.

Different projection systems have different strengths:
- Steamer: Skill-based, context-neutral, no playing time
- DepthChart: Blended, includes playing time, park/role adjustments
- ZiPS (future): Skill-based, different aging curves
- THE BAT (future): Component-based, different assumptions
- ATC (future): Consensus of multiple systems

Weights are optimized for fantasy baseball (counting stats vs. rate stats).
"""

# Projection weights by stat type
PROJECTION_WEIGHTS = {
    # Counting stats = skill × opportunity
    # DepthChart has playing time, so gets higher weight
    'counting_stats': {
        'depthchart': 0.70,  # Playing time is critical for counting stats
        'steamer': 0.30      # Skill check/floor
    },
    
    # Rate stats = pure skill
    # Steamer is context-neutral, so gets higher weight
    'rate_stats': {
        'steamer': 0.60,     # Context-neutral skill projection
        'depthchart': 0.40   # Context adjustments (park, league)
    },
    
    # Special cases
    'special': {
        'strikeouts': {
            'depthchart': 0.65,  # Opportunity matters, but skill is key
            'steamer': 0.35
        },
        'quality_starts': {
            'depthchart': 1.0    # Use DepthChart GS (has playing time)
        }
    }
}

# Stat categories
COUNTING_STATS = [
    'home_runs',
    'runs',
    'rbi',
    'stolen_bases',
    'wins',
    'saves',
    'holds'
]

RATE_STATS = [
    'on_base_percentage',
    'era',
    'whip'
]

# Strikeouts is a counting stat but skill-driven
SPECIAL_STATS = {
    'strikeouts': 'strikeouts',
    'quality_starts': 'quality_starts'
}

# Available projection systems (will expand as we add more)
AVAILABLE_SYSTEMS = ['steamer', 'depthchart']

# Future systems (when available)
FUTURE_SYSTEMS = ['zips', 'the_bat', 'atc']


def get_projection_weight(stat_name: str, system: str) -> float:
    """
    Get weight for a specific stat and projection system.
    
    Args:
        stat_name: Name of the stat (e.g., 'home_runs', 'era')
        system: Projection system (e.g., 'steamer', 'depthchart')
    
    Returns:
        Weight (0.0 to 1.0) for this stat/system combination
    """
    # Check special cases first
    if stat_name in SPECIAL_STATS:
        if stat_name == 'quality_starts':
            return PROJECTION_WEIGHTS['special']['quality_starts'].get(system, 0.0)
        elif stat_name == 'strikeouts':
            return PROJECTION_WEIGHTS['special']['strikeouts'].get(system, 0.0)
    
    # Determine if counting or rate stat
    if stat_name in COUNTING_STATS:
        return PROJECTION_WEIGHTS['counting_stats'].get(system, 0.0)
    elif stat_name in RATE_STATS:
        return PROJECTION_WEIGHTS['rate_stats'].get(system, 0.0)
    else:
        # Default: equal weighting for unknown stats
        return 0.5


def calculate_weighted_projection(stat_name: str, projections: dict) -> float:
    """
    Calculate weighted average projection for a stat.
    
    Args:
        stat_name: Name of the stat
        projections: Dict with projection systems as keys
                    e.g., {'steamer': 25.0, 'depthchart': 22.0}
    
    Returns:
        Weighted average projection
    """
    weighted_sum = 0.0
    total_weight = 0.0
    
    for system, value in projections.items():
        if value is not None and system in AVAILABLE_SYSTEMS:
            weight = get_projection_weight(stat_name, system)
            weighted_sum += value * weight
            total_weight += weight
    
    if total_weight == 0:
        # Fallback: simple average if no weights
        values = [v for v in projections.values() if v is not None]
        return sum(values) / len(values) if values else None
    
    return weighted_sum / total_weight if total_weight > 0 else None

