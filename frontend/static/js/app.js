import { ApiClient } from './api.js';
import { UIRenderer } from './ui-renderer.js';
import { DraftManager } from './draft-manager.js';
class App {
    constructor() {
        this.allPlayers = [];
        this.currentDraft = null;
        this.api = new ApiClient();
        this.renderer = new UIRenderer();
        this.draftManager = new DraftManager(this.api, this.renderer);
        this.initializeEventListeners();
        this.exposeGlobalMethods();
        this.loadInitialState();
    }
    exposeGlobalMethods() {
        window.draftPlayer = (playerId) => this.draftPlayerById(playerId);
        window.showTeamDetails = (teamName) => this.showTeamDetails(teamName);
        window.revertPick = (pickNumber) => this.revertPick(pickNumber);
    }
    async draftPlayerById(playerId) {
        const player = this.allPlayers.find(p => p.player_id === playerId);
        if (player) {
            await this.draftPlayer(player);
        }
    }
    initializeEventListeners() {
        // Load data buttons (optional - for manual reload)
        document.getElementById('load-cbs-btn')?.addEventListener('click', () => this.loadCBSData());
        document.getElementById('load-steamer-btn')?.addEventListener('click', () => this.loadSteamerFiles());
        // Search and filter
        document.getElementById('player-search')?.addEventListener('input', () => this.filterPlayers());
        document.getElementById('position-filter')?.addEventListener('change', () => this.filterPlayers());
    }
    async loadInitialState() {
        // Auto-load data on startup
        try {
            // Load CBS data first (source of truth for available players)
            await this.api.loadCBSData();
            // Then load Steamer projections (merges into master dictionary)
            await this.api.loadSteamerFiles();
        }
        catch (error) {
            console.error('Error auto-loading data:', error);
            // Continue anyway - user can manually reload if needed
        }
        // Try to load existing draft, or auto-create one
        let draft = await this.api.getCurrentDraft();
        if (!draft) {
            // Auto-create a default draft with first team as default
            draft = await this.api.createDraft({
                draft_id: 'draft_' + new Date().getTime(),
                league_name: 'Bob Uecker League',
                total_teams: 13,
                roster_size: 21,
                my_team_name: 'Runtime Terror' // Default to first team
            });
        }
        this.currentDraft = draft;
        await this.refreshAll();
        this.showApp();
    }
    async loadCBSData() {
        try {
            const result = await this.api.loadCBSData();
            if (result.success) {
                console.log(`Loaded CBS data: ${result.hitters} hitters, ${result.pitchers} pitchers`);
                await this.refreshAll();
            }
        }
        catch (error) {
            console.error('Error loading CBS data:', error);
            alert('Error loading CBS data');
        }
    }
    async loadSteamerFiles() {
        try {
            const result = await this.api.loadSteamerFiles();
            if (result.success) {
                console.log(`Loaded Steamer projections: ${result.hitters} hitters, ${result.pitchers} pitchers`);
                await this.refreshAll();
            }
        }
        catch (error) {
            console.error('Error loading Steamer files:', error);
            alert('Error loading Steamer files');
        }
    }
    async refreshAll() {
        await Promise.all([
            this.refreshPlayers(),
            this.refreshDraftStatus(),
            this.refreshAvailablePlayers(),
            this.refreshMyTeam(),
            this.refreshRecentPicks(),
            this.refreshOtherTeams()
        ]);
    }
    async refreshPlayers() {
        this.allPlayers = await this.api.getAllPlayers();
    }
    async refreshDraftStatus() {
        if (!this.currentDraft)
            return;
        this.renderer.updateDraftStatusBar(this.currentDraft);
    }
    async refreshAvailablePlayers() {
        const available = await this.api.getAvailablePlayers();
        this.renderer.renderAvailablePlayers(available, (player) => this.draftPlayer(player));
    }
    async refreshMyTeam() {
        if (!this.currentDraft)
            return;
        const myTeam = await this.api.getMyTeam();
        this.renderer.renderMyTeam(this.currentDraft.my_team_name, myTeam, this.currentDraft);
    }
    async refreshRecentPicks() {
        if (!this.currentDraft)
            return;
        const recentPicks = this.currentDraft.picks.slice(-20).reverse();
        const pickDetails = recentPicks.map(pick => {
            const player = this.allPlayers.find(p => p.player_id === pick.player_id);
            return { pick, player: player || null };
        });
        this.renderer.renderRecentPicks(pickDetails, (pickNumber) => this.revertPick(pickNumber));
    }
    async revertPick(pickNumber) {
        if (!this.currentDraft) {
            alert('No active draft');
            return;
        }
        if (!confirm(`Are you sure you want to revert pick #${pickNumber}?`)) {
            return;
        }
        try {
            this.currentDraft = await this.api.revertPick(pickNumber);
            await this.refreshAll();
        }
        catch (error) {
            console.error('Error reverting pick:', error);
            alert('Error reverting pick');
        }
    }
    async refreshOtherTeams() {
        if (!this.currentDraft)
            return;
        const teams = [];
        for (const [teamName, playerIds] of Object.entries(this.currentDraft.team_rosters)) {
            if (teamName !== this.currentDraft.my_team_name) {
                const players = playerIds
                    .map(id => this.allPlayers.find(p => p.player_id === id))
                    .filter((p) => p !== undefined);
                teams.push({ teamName, players });
            }
        }
        this.renderer.renderOtherTeams(teams, (teamName) => this.showTeamDetails(teamName));
    }
    async draftPlayer(player) {
        if (!this.currentDraft) {
            alert('No active draft');
            return;
        }
        try {
            this.currentDraft = await this.api.makePick(player.player_id, this.currentDraft.my_team_name);
            await this.refreshAll();
        }
        catch (error) {
            console.error('Error drafting player:', error);
            alert('Error drafting player');
        }
    }
    async showTeamDetails(teamName) {
        const players = await this.api.getTeam(teamName);
        // Show team details in a modal or alert for now
        const playerList = players.map(p => `- ${p.name} (${p.position})`).join('\n');
        alert(`${teamName} (${players.length} players):\n\n${playerList}`);
    }
    filterPlayers() {
        const searchTerm = document.getElementById('player-search')?.value.toLowerCase() || '';
        const positionFilter = document.getElementById('position-filter')?.value || '';
        // This will be handled by the renderer when we refresh available players
        this.refreshAvailablePlayers();
    }
    showApp() {
        const app = document.getElementById('app');
        if (app)
            app.style.display = 'block';
    }
}
// Initialize app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new App());
}
else {
    new App();
}
//# sourceMappingURL=app.js.map