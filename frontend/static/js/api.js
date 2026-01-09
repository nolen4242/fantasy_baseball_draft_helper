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
        }
        catch (error) {
            console.error('Error fetching available players:', error);
            return [];
        }
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
        }
        catch (error) {
            console.error('Error fetching recommendations:', error);
            return [];
        }
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
        }
        catch (error) {
            console.error('Error in toggleAutoDraft:', error);
            throw error;
        }
    }
    async getAutoDraftStatus() {
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
        }
        catch (error) {
            console.error('Error in getAutoDraftStatus:', error);
            throw error;
        }
    }
    async makeAutoDraftPick(teamName) {
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
        }
        catch (error) {
            console.error('Error in makeAutoDraftPick:', error);
            throw error;
        }
    }
    async getStandings() {
        const response = await fetch(`${API_BASE}/api/standings`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    }
    async trainMLModels() {
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
    async getDraftBoard() {
        const response = await fetch(`${API_BASE}/api/draft/board`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    }
}
//# sourceMappingURL=api.js.map