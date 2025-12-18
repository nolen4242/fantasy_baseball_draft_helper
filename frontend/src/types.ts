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

