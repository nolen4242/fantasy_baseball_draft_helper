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
    private autoDraftEnabled: boolean = false;

    constructor() {
        this.api = new ApiClient();
        this.renderer = new UIRenderer(this.api);
        this.draftManager = new DraftManager(this.api, this.renderer);
        this.initializeEventListeners();
        this.exposeGlobalMethods();
        this.loadInitialState();
        
        // Listen for player move events
        window.addEventListener('playerMoved', () => {
            this.refreshMyTeam();
        });
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
        document.getElementById('restart-draft-btn')?.addEventListener('click', () => this.restartDraft());
        document.getElementById('auto-draft-toggle-btn')?.addEventListener('click', () => this.toggleAutoDraft());
        
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
        
        // Load auto-draft status
        try {
            const status = await this.api.getAutoDraftStatus();
            this.autoDraftEnabled = status.auto_draft_enabled;
            this.updateAutoDraftButton();
        } catch (error) {
            console.error('Error loading auto-draft status:', error);
        }
        
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

    private async restartDraft(): Promise<void> {
        if (!confirm('Are you sure you want to clear all rosters? This will remove ALL players from ALL teams and reset all roster spots.')) {
            return;
        }
        
        try {
            const result = await this.api.restartDraft();
            if (result.draft) {
                this.currentDraft = result.draft;
            } else {
                this.currentDraft = null;
            }
            await this.refreshAll();
            alert(result.message || 'All team rosters cleared successfully!');
        } catch (error) {
            console.error('Error restarting draft:', error);
            alert('Error clearing rosters: ' + (error instanceof Error ? error.message : 'Unknown error'));
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
        
        // Check if auto-draft should trigger
        if (this.autoDraftEnabled) {
            await this.checkAndTriggerAutoDraft();
        }
    }
    
    private async checkAndTriggerAutoDraft(): Promise<void> {
        if (!this.currentDraft) return;
        
        // Don't auto-draft if draft is complete
        if (this.currentDraft.is_complete) {
            return;
        }
        
        // Determine whose turn it is
        const pickNumber = this.currentDraft.picks.length + 1;
        const round = Math.floor((pickNumber - 1) / this.currentDraft.total_teams) + 1;
        const pickInRound = ((pickNumber - 1) % this.currentDraft.total_teams) + 1;
        
        // Bob Uecker League: Rounds 1-5 no snake, Round 6+ snakes
        const teamOrder = [
            "Runtime Terror",
            "Dawg",
            "Long Balls",
            "Simba's Dublin Green Sox",
            "Young Guns",
            "Gashouse Gang",
            "Magnum GI",
            "Trex",
            "Rieken Havoc",
            "Guillotine",
            "MAGA DOGE",
            "Big Sticks",
            "Like a Nightmare"
        ];
        
        let currentTeam: string;
        if (round <= 5) {
            currentTeam = teamOrder[pickInRound - 1];
        } else {
            const snakeRound = round - 5;
            const isOddSnakeRound = snakeRound % 2 === 1;
            if (isOddSnakeRound) {
                currentTeam = teamOrder[this.currentDraft.total_teams - pickInRound];
            } else {
                currentTeam = teamOrder[pickInRound - 1];
            }
        }
        
        // Only auto-draft if it's not the user's team
        if (currentTeam !== this.currentDraft.my_team_name) {
            try {
                // Check if this team's roster is full
                const teamRosterSize = this.currentDraft.team_rosters[currentTeam]?.length || 0;
                if (teamRosterSize >= this.currentDraft.roster_size) {
                    // Team roster is full, skip auto-draft
                    return;
                }
                
                console.log(`Auto-drafting for ${currentTeam}...`);
                const result = await this.api.makeAutoDraftPick(currentTeam);
                this.currentDraft = result.draft;
                console.log(`Auto-drafted ${result.picked_player.name} for ${currentTeam}. Reasoning: ${result.reasoning}`);
                
                // Check if draft is now complete
                if (result.draft_complete) {
                    console.log('Draft Complete! All roster spots filled.');
                }
                
                // Refresh everything after auto-draft
                await this.refreshAll();
                
                // If draft not complete, continue auto-drafting
                if (!result.draft_complete && this.autoDraftEnabled) {
                    setTimeout(() => this.checkAndTriggerAutoDraft(), 100);
                }
            } catch (error) {
                console.error('Error making auto-draft pick:', error);
                // If error is about roster being full or draft complete, that's okay
                const errorMessage = error instanceof Error ? error.message : '';
                if (!errorMessage.includes('full') && !errorMessage.includes('complete')) {
                    // Only log unexpected errors
                }
            }
        }
    }
    
    private async toggleAutoDraft(): Promise<void> {
        try {
            const newState = !this.autoDraftEnabled;
            const result = await this.api.toggleAutoDraft(newState);
            this.autoDraftEnabled = result.auto_draft_enabled;
            this.updateAutoDraftButton();
            
            if (this.autoDraftEnabled) {
                // Check if we should immediately trigger auto-draft
                await this.checkAndTriggerAutoDraft();
            }
        } catch (error) {
            console.error('Error toggling auto-draft:', error);
            alert('Error toggling auto-draft');
        }
    }
    
    private updateAutoDraftButton(): void {
        const btn = document.getElementById('auto-draft-toggle-btn');
        if (btn) {
            btn.textContent = `Auto-Draft: ${this.autoDraftEnabled ? 'ON' : 'OFF'}`;
            if (this.autoDraftEnabled) {
                btn.classList.add('btn-active');
            } else {
                btn.classList.remove('btn-active');
            }
        }
    }

    private async refreshAvailablePlayers(): Promise<void> {
        const available = await this.api.getAvailablePlayers();
        const draftComplete = this.currentDraft?.is_complete || false;
        this.renderer.renderAvailablePlayers(available, (player) => this.draftPlayer(player), draftComplete);
    }

    private async refreshMyTeam(): Promise<void> {
        if (!this.currentDraft) return;
        const result = await this.api.getMyTeam();
        this.renderer.renderMyTeam(
            this.currentDraft.my_team_name, 
            result.players, 
            this.currentDraft,
            result.roster
        );
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

        // Note: We allow drafting even if draft is marked complete, as long as required positions aren't filled
        // The backend will check if the team can actually draft more players

        try {
            // If no draft exists, the backend will auto-create one
            const teamName = this.currentDraft?.my_team_name || 'Runtime Terror';
            const result = await this.api.makePick(player.player_id, teamName);
            this.currentDraft = result;
            
            // Check if draft is now complete
            if (result.is_complete) {
                alert('Draft Complete! All roster spots have been filled.');
            }
            
            await this.refreshAll();
            
            // After user picks, check if auto-draft should trigger for next team
            if (this.autoDraftEnabled && !result.is_complete) {
                // Small delay to ensure state is updated
                setTimeout(() => this.checkAndTriggerAutoDraft(), 100);
            }
        } catch (error) {
            console.error('Error drafting player:', error);
            const errorMessage = error instanceof Error ? error.message : 'Error drafting player';
            alert(errorMessage);
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

