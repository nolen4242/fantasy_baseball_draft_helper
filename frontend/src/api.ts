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
        // Return the draft with is_complete flag
        const draft = data.draft || {};
        return { ...draft, is_complete: data.draft_complete || draft.is_complete || false };
    }

    async getAvailablePlayers(): Promise<Player[]> {
        try {
            const response = await fetch(`${API_BASE}/api/draft/available`);
            if (!response.ok) {
                console.error('Error fetching available players:', response.status, response.statusText);
                const errorData = await response.json().catch(() => ({}));
                console.error('Error details:', errorData);
                return [];
            }
            const data = await response.json();
            console.log(`✅ Loaded ${data.players?.length || 0} available players`);
            return data.players || [];
        } catch (error) {
            console.error('Error fetching available players:', error);
            return [];
        }
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
        try {
            const response = await fetch(`${API_BASE}/api/recommendations`);
            if (!response.ok) {
                console.error('Recommendations API error:', response.status, response.statusText);
                return [];
            }
            const data = await response.json();
            console.log('Recommendations API response:', data);
            const recommendations = data.recommendations || [];
            console.log(`Got ${recommendations.length} recommendations`);
            return recommendations;
        } catch (error) {
            console.error('Error fetching recommendations:', error);
            return [];
        }
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

    async restartDraft(): Promise<{ success: boolean; draft?: DraftState; message: string }> {
        const response = await fetch(`${API_BASE}/api/draft/restart`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.message || 'Failed to restart draft');
        }
        return {
            success: data.success,
            draft: data.draft || undefined,
            message: data.message || 'Draft restarted successfully'
        };
    }

    async toggleAutoDraft(enabled: boolean): Promise<{ success: boolean; auto_draft_enabled: boolean }> {
        try {
            const response = await fetch(`${API_BASE}/api/draft/auto-draft/toggle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });
            
            // Check if response is actually JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                console.error('Non-JSON response received:', text.substring(0, 200));
                throw new Error(`Server returned ${response.status}: Expected JSON but got ${contentType}`);
            }
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: 'Failed to toggle auto-draft' }));
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('Error in toggleAutoDraft:', error);
            throw error;
        }
    }

    async getAutoDraftStatus(): Promise<{ auto_draft_enabled: boolean }> {
        try {
            const response = await fetch(`${API_BASE}/api/draft/auto-draft/status`);
            
            // Check if response is actually JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                console.error('Non-JSON response received:', text.substring(0, 200));
                throw new Error(`Server returned ${response.status}: Expected JSON but got ${contentType}`);
            }
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: 'Failed to get auto-draft status' }));
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('Error in getAutoDraftStatus:', error);
            throw error;
        }
    }

    async makeAutoDraftPick(teamName: string): Promise<{ 
        success: boolean; 
        draft: DraftState; 
        picked_player: Player;
        reasoning: string;
        draft_complete?: boolean;
    }> {
        try {
            const response = await fetch(`${API_BASE}/api/draft/auto-draft/pick`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ team_name: teamName })
            });
            
            // Check if response is actually JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                console.error('Non-JSON response received:', text.substring(0, 200));
                throw new Error(`Server returned ${response.status}: Expected JSON but got ${contentType}`);
            }
            
            const data = await response.json();
            if (!data.success) {
                throw new Error(data.message || 'Failed to make auto-draft pick');
            }
            return data;
        } catch (error) {
            console.error('Error in makeAutoDraftPick:', error);
            throw error;
        }
    }

    async getStandings(): Promise<{
        success: boolean;
        standings: Array<{
            rank: number;
            team_name: string;
            total_points: number;
            category_totals: Record<string, number>;
            category_ranks: Record<string, number>;
        }>;
        category_rankings: Record<string, string[]>;
        categories: {
            batting: string[];
            pitching: string[];
        };
    }> {
        const response = await fetch(`${API_BASE}/api/standings`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    }

    async trainMLModels(): Promise<{
        success: boolean;
        message: string;
        samples?: number;
        features?: number;
        rf_train_score?: number;
        rf_test_score?: number;
        gb_train_score?: number;
        gb_test_score?: number;
        ensemble_train_score?: number;
        ensemble_test_score?: number;
        top_features?: Record<string, number>;
        models_dir?: string;
    }> {
        const response = await fetch(`${API_BASE}/api/ml/train`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
        }
        
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            throw new Error(`Expected JSON but got ${contentType}: ${text.substring(0, 200)}`);
        }
        
        return response.json();
    }

    async getDraftBoard(): Promise<{
        success: boolean;
        board: {
            teams: Array<{
                name: string;
                color: string;
                player_count: number;
                positions: Record<string, { player_id: string; name: string; position: string; adp?: number }>;
                is_my_team: boolean;
            }>;
            position_slots: string[];
            current_pick: number;
            current_round: number;
            my_team: string;
        };
    }> {
        const response = await fetch(`${API_BASE}/api/draft/board`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    }
}

