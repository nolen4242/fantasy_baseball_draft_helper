const API_BASE = '';
export class ApiClient {
    async loadPlayers(filename) {
        const response = await fetch(`${API_BASE}/api/players/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
        return response.json();
    }
    async loadSteamerFiles() {
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
    async loadCBSData() {
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
    async getAllPlayers() {
        const response = await fetch(`${API_BASE}/api/players`);
        const data = await response.json();
        return data.players || [];
    }
    async createDraft(draftData) {
        const response = await fetch(`${API_BASE}/api/draft/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(draftData)
        });
        const data = await response.json();
        return data.draft;
    }
    async getCurrentDraft() {
        const response = await fetch(`${API_BASE}/api/draft/current`);
        if (response.status === 404)
            return null;
        const data = await response.json();
        return data.draft || null;
    }
    async makePick(playerId, teamName) {
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
    async getAvailablePlayers() {
        const response = await fetch(`${API_BASE}/api/draft/available`);
        const data = await response.json();
        return data.players || [];
    }
    async getMyTeam() {
        const response = await fetch(`${API_BASE}/api/draft/my-team`);
        const data = await response.json();
        return {
            players: data.players || [],
            roster: data.roster || null
        };
    }
    async movePlayerPosition(playerId, fromPosition, fromIndex, toPosition, toIndex, teamName) {
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
    async getTeam(teamName) {
        const response = await fetch(`${API_BASE}/api/draft/team/${encodeURIComponent(teamName)}`);
        const data = await response.json();
        return data.players || [];
    }
    async getRecommendations() {
        const response = await fetch(`${API_BASE}/api/recommendations`);
        const data = await response.json();
        return data.recommendations || [];
    }
    async revertPick(pickNumber) {
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
    async restartDraft() {
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
    async toggleAutoDraft(enabled) {
        const response = await fetch(`${API_BASE}/api/draft/auto-draft/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        return response.json();
    }
    async getAutoDraftStatus() {
        const response = await fetch(`${API_BASE}/api/draft/auto-draft/status`);
        return response.json();
    }
    async makeAutoDraftPick(teamName) {
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
    async getStandings() {
        const response = await fetch(`${API_BASE}/api/standings`);
        return response.json();
    }
    async getDraftBoard() {
        const response = await fetch(`${API_BASE}/api/draft/board`);
        return response.json();
    }
    async getPlayerAnalysis(playerId) {
        const response = await fetch(`${API_BASE}/api/player/${playerId}/analysis`);
        return response.json();
    }
    async getEligiblePositions(playerId) {
        const response = await fetch(`${API_BASE}/api/player/${playerId}/eligible-positions`);
        return response.json();
    }
    async getCategoryNeeds() {
        const response = await fetch(`${API_BASE}/api/team/category-needs`);
        return response.json();
    }
    async batchRevert(revertToPick) {
        const response = await fetch(`${API_BASE}/api/draft/batch-revert`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ revert_to_pick: revertToPick })
        });
        const data = await response.json();
        if (!data.success)
            throw new Error(data.message || 'Failed to batch revert');
        return data.draft;
    }
    async setStrategy(strategy) {
        const response = await fetch(`${API_BASE}/api/draft/strategy`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ strategy })
        });
        return response.json();
    }
    async getStrategy() {
        const response = await fetch(`${API_BASE}/api/draft/strategy`);
        return response.json();
    }
    async analyzeTrade(teamA, teamB, playersFromA, playersFromB) {
        const response = await fetch(`${API_BASE}/api/trade/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ team_a: teamA, team_b: teamB, players_from_a: playersFromA, players_from_b: playersFromB })
        });
        return response.json();
    }
    async getWinProbability(iterations) {
        const url = iterations ? `${API_BASE}/api/draft/win-probability?iterations=${iterations}` : `${API_BASE}/api/draft/win-probability`;
        const response = await fetch(url);
        return response.json();
    }
    async getDraftRecap() {
        const response = await fetch(`${API_BASE}/api/draft/recap`);
        return response.json();
    }
}
//# sourceMappingURL=api.js.map