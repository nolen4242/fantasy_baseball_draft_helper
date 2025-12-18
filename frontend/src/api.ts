import { Player, DraftState, Recommendation, TeamRoster } from './types.js';

const API_BASE = '';

export class ApiClient {
    async loadPlayers(filename: string): Promise<{ success: boolean; count: number; warning?: string }> {
        const response = await fetch(`${API_BASE}/api/players/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
        return response.json();
    }

    async loadSteamerFiles(): Promise<{ 
        success: boolean; 
        count: number; 
        hitters: number; 
        pitchers: number; 
        warning?: string 
    }> {
        const response = await fetch(`${API_BASE}/api/players/load-steamer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                hitter_file: 'steamer-batters.csv',
                pitcher_file: 'steamer-pitchers.csv'
            })
        });
        return response.json();
    }

    async loadCBSData(): Promise<{ 
        success: boolean; 
        count: number; 
        hitters: number; 
        pitchers: number; 
        message?: string 
    }> {
        const response = await fetch(`${API_BASE}/api/players/load-cbs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                hitter_file: 'cbs-batter-2025.csv',
                pitcher_file: 'cbs-pitchers-2025.csv'
            })
        });
        return response.json();
    }

    async getAllPlayers(): Promise<Player[]> {
        const response = await fetch(`${API_BASE}/api/players`);
        const data = await response.json();
        return data.players || [];
    }

    async createDraft(draftData: {
        draft_id: string;
        league_name: string;
        total_teams: number;
        roster_size: number;
        my_team_name: string;
    }): Promise<DraftState> {
        const response = await fetch(`${API_BASE}/api/draft/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(draftData)
        });
        const data = await response.json();
        return data.draft;
    }

    async getCurrentDraft(): Promise<DraftState | null> {
        const response = await fetch(`${API_BASE}/api/draft/current`);
        if (response.status === 404) return null;
        const data = await response.json();
        return data.draft || null;
    }

    async makePick(playerId: string, teamName: string): Promise<DraftState & { is_complete?: boolean }> {
        const response = await fetch(`${API_BASE}/api/draft/pick`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ player_id: playerId, team_name: teamName })
        });
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.message || 'Failed to make pick');
        }
        return { ...data.draft, is_complete: data.draft_complete || false };
    }

    async getAvailablePlayers(): Promise<Player[]> {
        const response = await fetch(`${API_BASE}/api/draft/available`);
        const data = await response.json();
        return data.players || [];
    }

    async getMyTeam(): Promise<{ players: Player[]; roster: any }> {
        const response = await fetch(`${API_BASE}/api/draft/my-team`);
        const data = await response.json();
        return {
            players: data.players || [],
            roster: data.roster || null
        };
    }

    async movePlayerPosition(
        playerId: string,
        fromPosition: string,
        fromIndex: number,
        toPosition: string,
        toIndex: number,
        teamName: string
    ): Promise<{ success: boolean; roster: any }> {
        const response = await fetch(`${API_BASE}/api/draft/move-player`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                player_id: playerId,
                from_position: fromPosition,
                from_index: fromIndex,
                to_position: toPosition,
                to_index: toIndex,
                team_name: teamName
            })
        });
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.message || 'Failed to move player');
        }
        return data;
    }

    async getTeam(teamName: string): Promise<Player[]> {
        const response = await fetch(`${API_BASE}/api/draft/team/${encodeURIComponent(teamName)}`);
        const data = await response.json();
        return data.players || [];
    }

    async getRecommendations(): Promise<Recommendation[]> {
        const response = await fetch(`${API_BASE}/api/recommendations`);
        const data = await response.json();
        return data.recommendations || [];
    }

    async revertPick(pickNumber: number): Promise<DraftState> {
        const response = await fetch(`${API_BASE}/api/draft/revert`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pick_number: pickNumber })
        });
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.message || 'Failed to revert pick');
        }
        return data.draft;
    }

    async restartDraft(): Promise<DraftState> {
        const response = await fetch(`${API_BASE}/api/draft/restart`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.message || 'Failed to restart draft');
        }
        return data.draft;
    }

    async toggleAutoDraft(enabled: boolean): Promise<{ success: boolean; auto_draft_enabled: boolean }> {
        const response = await fetch(`${API_BASE}/api/draft/auto-draft/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        return response.json();
    }

    async getAutoDraftStatus(): Promise<{ auto_draft_enabled: boolean }> {
        const response = await fetch(`${API_BASE}/api/draft/auto-draft/status`);
        return response.json();
    }

    async makeAutoDraftPick(teamName: string): Promise<{ 
        success: boolean; 
        draft: DraftState; 
        picked_player: Player;
        reasoning: string;
        draft_complete?: boolean;
    }> {
        const response = await fetch(`${API_BASE}/api/draft/auto-draft/pick`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ team_name: teamName })
        });
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.message || 'Failed to make auto-draft pick');
        }
        return data;
    }
}

