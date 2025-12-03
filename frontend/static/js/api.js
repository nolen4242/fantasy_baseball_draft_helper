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
        return data.draft;
    }
    async getAvailablePlayers() {
        const response = await fetch(`${API_BASE}/api/draft/available`);
        const data = await response.json();
        return data.players || [];
    }
    async getMyTeam() {
        const response = await fetch(`${API_BASE}/api/draft/my-team`);
        const data = await response.json();
        return data.players || [];
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
        return data.draft;
    }
}
//# sourceMappingURL=api.js.map