import { ApiClient } from './api.js';
import { Player, DraftState, Recommendation, TeamRoster } from './types.js';
import { UIRenderer } from './ui-renderer.js';
import { DraftManager } from './draft-manager.js';

class App {
    private api: ApiClient;
    private renderer: UIRenderer;
    private draftManager: DraftManager;
    private allPlayers: Player[] = [];
    private currentDraft: DraftState | null = null;

    constructor() {
        this.api = new ApiClient();
        this.renderer = new UIRenderer();
        this.draftManager = new DraftManager(this.api, this.renderer);
        this.initializeEventListeners();
        this.exposeGlobalMethods();
        this.loadInitialState();
    }

    private exposeGlobalMethods(): void {
        (window as any).draftPlayer = (playerId: string) => this.draftPlayerById(playerId);
        (window as any).showTeamDetails = (teamName: string) => this.showTeamDetails(teamName);
        (window as any).revertPick = (pickNumber: number) => this.revertPick(pickNumber);
    }

    private async draftPlayerById(playerId: string): Promise<void> {
        const player = this.allPlayers.find(p => p.player_id === playerId);
        if (player) {
            await this.draftPlayer(player);
        }
    }

    private initializeEventListeners(): void {
        // Load data buttons (optional - for manual reload)
        document.getElementById('load-cbs-btn')?.addEventListener('click', () => this.loadCBSData());
        document.getElementById('load-steamer-btn')?.addEventListener('click', () => this.loadSteamerFiles());
        
        // Search and filter
        document.getElementById('player-search')?.addEventListener('input', () => this.filterPlayers());
        document.getElementById('position-filter')?.addEventListener('change', () => this.filterPlayers());
    }

    private async loadInitialState(): Promise<void> {
        // Auto-load data on startup
        try {
            // Load CBS data first (source of truth for available players)
            await this.api.loadCBSData();
            // Then load Steamer projections (merges into master dictionary)
            await this.api.loadSteamerFiles();
        } catch (error) {
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
                my_team_name: 'Runtime Terror'  // Default to first team
            });
        }
        this.currentDraft = draft;
        await this.refreshAll();
        this.showApp();
    }

    private async loadCBSData(): Promise<void> {
        try {
            const result = await this.api.loadCBSData();
            if (result.success) {
                console.log(`Loaded CBS data: ${result.hitters} hitters, ${result.pitchers} pitchers`);
                await this.refreshAll();
            }
        } catch (error) {
            console.error('Error loading CBS data:', error);
            alert('Error loading CBS data');
        }
    }

    private async loadSteamerFiles(): Promise<void> {
        try {
            const result = await this.api.loadSteamerFiles();
            if (result.success) {
                console.log(`Loaded Steamer projections: ${result.hitters} hitters, ${result.pitchers} pitchers`);
                await this.refreshAll();
            }
        } catch (error) {
            console.error('Error loading Steamer files:', error);
            alert('Error loading Steamer files');
        }
    }


    private async refreshAll(): Promise<void> {
        await Promise.all([
            this.refreshPlayers(),
            this.refreshDraftStatus(),
            this.refreshAvailablePlayers(),
            this.refreshMyTeam(),
            this.refreshRecentPicks(),
            this.refreshOtherTeams()
        ]);
    }

    private async refreshPlayers(): Promise<void> {
        this.allPlayers = await this.api.getAllPlayers();
    }

    private async refreshDraftStatus(): Promise<void> {
        if (!this.currentDraft) return;
        
        // Get top recommendation
        let topRecommendation = null;
        try {
            const recommendations = await this.api.getRecommendations();
            if (recommendations && recommendations.length > 0) {
                topRecommendation = recommendations[0];
            }
        } catch (error) {
            console.error('Error fetching recommendations:', error);
        }
        
        this.renderer.updateDraftStatusBar(this.currentDraft, topRecommendation);
    }

    private async refreshAvailablePlayers(): Promise<void> {
        const available = await this.api.getAvailablePlayers();
        this.renderer.renderAvailablePlayers(available, (player) => this.draftPlayer(player));
    }

    private async refreshMyTeam(): Promise<void> {
        if (!this.currentDraft) return;
        const myTeam = await this.api.getMyTeam();
        this.renderer.renderMyTeam(this.currentDraft.my_team_name, myTeam, this.currentDraft);
    }

    private async refreshRecentPicks(): Promise<void> {
        if (!this.currentDraft) return;
        const recentPicks = this.currentDraft.picks.slice(-20).reverse();
        const pickDetails = recentPicks.map(pick => {
            const player = this.allPlayers.find(p => p.player_id === pick.player_id);
            return { pick, player: player || null };
        });
        this.renderer.renderRecentPicks(pickDetails, (pickNumber) => this.revertPick(pickNumber));
    }
    
    private async revertPick(pickNumber: number): Promise<void> {
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
        } catch (error) {
            console.error('Error reverting pick:', error);
            alert('Error reverting pick');
        }
    }

    private async refreshOtherTeams(): Promise<void> {
        if (!this.currentDraft) return;
        const teams: TeamRoster[] = [];
        
        for (const [teamName, playerIds] of Object.entries(this.currentDraft.team_rosters)) {
            if (teamName !== this.currentDraft.my_team_name) {
                const players = playerIds
                    .map(id => this.allPlayers.find(p => p.player_id === id))
                    .filter((p): p is Player => p !== undefined);
                teams.push({ teamName, players });
            }
        }

        this.renderer.renderOtherTeams(teams, (teamName) => this.showTeamDetails(teamName));
    }

    private async draftPlayer(player: Player): Promise<void> {
        if (!this.currentDraft) {
            alert('No active draft');
            return;
        }

        try {
            this.currentDraft = await this.api.makePick(player.player_id, this.currentDraft.my_team_name);
            await this.refreshAll();
        } catch (error) {
            console.error('Error drafting player:', error);
            alert('Error drafting player');
        }
    }

    private async showTeamDetails(teamName: string): Promise<void> {
        const players = await this.api.getTeam(teamName);
        // Show team details in a modal or alert for now
        const playerList = players.map(p => `- ${p.name} (${p.position})`).join('\n');
        alert(`${teamName} (${players.length} players):\n\n${playerList}`);
    }

    private filterPlayers(): void {
        const searchTerm = (document.getElementById('player-search') as HTMLInputElement)?.value.toLowerCase() || '';
        const positionFilter = (document.getElementById('position-filter') as HTMLSelectElement)?.value || '';
        
        // This will be handled by the renderer when we refresh available players
        this.refreshAvailablePlayers();
    }

    private showApp(): void {
        const app = document.getElementById('app');
        if (app) app.style.display = 'block';
    }
}

// Initialize app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new App());
} else {
    new App();
}

