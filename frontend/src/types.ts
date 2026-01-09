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

export interface BlockingOpportunity {
    team: string;
    position: string;
    urgency: number;
    impact: string;
}

export interface VORPData {
    score: number;
    tier: string;
    category_contributions: Record<string, number>;
}

export interface ScarcityTier {
    tier: string;
    elite_remaining: number;
}

export interface Recommendation {
    player: Player;
    score: number;
    reasoning: string;
    vorp?: VORPData;
    blocking?: BlockingOpportunity[];
    scarcity_tier?: ScarcityTier;
    category_gaps?: Record<string, number>;
}

export interface DraftBoardTeam {
    name: string;
    color: string;
    player_count: number;
    positions: Record<string, { player_id: string; name: string; position: string; adp?: number }>;
    is_my_team: boolean;
}

export interface DraftBoard {
    teams: DraftBoardTeam[];
    position_slots: string[];
    current_pick: number;
    current_round: number;
    my_team: string;
}

export interface TeamRoster {
    teamName: string;
    players: Player[];
}

export interface StandingsTeam {
    rank: number;
    team_name: string;
    total_points: number;
    category_totals: Record<string, number>;
    category_ranks: Record<string, number>;
    category_points?: Record<string, number>;  // Add category_points
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

