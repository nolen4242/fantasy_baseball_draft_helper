// Type definitions for the application

export interface Player {
    player_id: string;
    name: string;
    position: string;
    team: string;
    age?: number;
    projected_home_runs?: number;
    projected_obp?: number;
    projected_runs?: number;
    projected_rbi?: number;
    projected_stolen_bases?: number;
    projected_wins?: number;
    projected_quality_starts?: number;
    projected_strikeouts?: number;
    projected_era?: number;
    projected_whip?: number;
    projected_saves?: number;
    projected_holds?: number;
    drafted?: boolean;
    drafted_by_team?: string;
    draft_round?: number;
    draft_pick?: number;
    adp?: number;  // Average Draft Position
}

export interface DraftPick {
    pick_number: number;
    round: number;
    team_name: string;
    player_id: string;
    timestamp: string;
}

export interface DraftState {
    draft_id: string;
    league_name: string;
    total_teams: number;
    roster_size: number;
    my_team_name: string;
    current_pick: number;
    current_round: number;
    picks: DraftPick[];
    team_rosters: { [teamName: string]: string[] };
    is_complete?: boolean;
}

export interface Recommendation {
    player: Player;
    score: number;
    reasoning: string;
}

export interface TeamRoster {
    teamName: string;
    players: Player[];
}

export interface RosterPosition {
    [position: string]: (PlayerEntry | null)[];
}

export interface PlayerEntry {
    player_id: string;
    name: string;
    position: string;
    team: string;
    pick_number?: number;
    round?: number;
    stats?: any;
}

export interface CategoryNeed {
    category: string;
    value: number;
    rank: number;
    need: 'critical' | 'moderate' | 'good' | 'strong';
}

export interface TradeAnalysis {
    before_standings: { team_a_rank: number; team_a_points: number; team_b_rank: number; team_b_points: number };
    after_standings: { team_a_rank: number; team_a_points: number; team_b_rank: number; team_b_points: number };
    category_impact: { [cat: string]: { team_a_before: number; team_a_after: number; team_b_before: number; team_b_after: number } };
}

export interface DraftRecap {
    teams: Array<{
        team_name: string;
        player_count: number;
        batting_points: number;
        pitching_points: number;
        total_points: number;
        grade: string;
        best_pick: { player_name: string; adp: number; pick_number: number } | null;
        biggest_reach: { player_name: string; adp: number; pick_number: number } | null;
    }>;
}

