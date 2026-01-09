import { ApiClient } from './api.js';
import { UIRenderer } from './ui-renderer.js';
import { DraftManager } from './draft-manager.js';
class App {
    constructor() {
        this.currentRecommendation = null;
        this.topRecommendations = [];
        this.allPlayers = [];
        this.currentDraft = null;
        this.autoDraftEnabled = false;
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
    exposeGlobalMethods() {
        window.draftPlayer = (playerId) => this.draftPlayerById(playerId);
        window.showTeamDetails = (teamName) => this.showTeamDetails(teamName);
        window.revertPick = (pickNumber) => this.revertPick(pickNumber);
    }
    showRecommendationAnalysis() {
        if (!this.currentRecommendation) {
            return;
        }
        const modal = document.getElementById('recommendation-modal');
        const modalTitle = document.getElementById('recommendation-modal-title');
        const modalBody = document.getElementById('recommendation-modal-body');
        if (!modal || !modalTitle || !modalBody)
            return;
        // Set title
        modalTitle.textContent = `${this.currentRecommendation.player.name} - Detailed Analysis`;
        // Use enhanced rendering if we have the new data
        if (this.currentRecommendation.vorp || this.currentRecommendation.blocking) {
            modalBody.innerHTML = this.renderer.renderEnhancedRecommendation(this.currentRecommendation);
        }
        else {
            // Fallback to basic reasoning
            const reasoning = this.currentRecommendation.reasoning || 'No analysis available.';
            const formattedReasoning = reasoning.split('\n\n').map(section => {
                return `<div class="analysis-section">${section}</div>`;
            }).join('');
            modalBody.innerHTML = formattedReasoning;
        }
        // Show modal
        modal.style.display = 'block';
    }
    closeRecommendationModal() {
        const modal = document.getElementById('recommendation-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }
    async showDraftBoard() {
        try {
            const result = await this.api.getDraftBoard();
            if (result.success && result.board) {
                this.renderer.renderDraftBoard(result.board);
                const modal = document.getElementById('draft-board-modal');
                if (modal) {
                    modal.style.display = 'block';
                }
            }
            else {
                alert('Failed to load draft board.');
            }
        }
        catch (error) {
            console.error('Error loading draft board:', error);
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            alert('Error loading draft board: ' + errorMessage);
        }
    }
    closeDraftBoardModal() {
        const modal = document.getElementById('draft-board-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }
    async draftPlayerById(playerId) {
        const player = this.allPlayers.find(p => p.player_id === playerId);
        if (player) {
            await this.draftPlayer(player);
        }
    }
    initializeEventListeners() {
        // Draft action buttons
        document.getElementById('restart-draft-btn')?.addEventListener('click', () => this.restartDraft());
        document.getElementById('view-standings-btn')?.addEventListener('click', () => this.showStandings());
        document.getElementById('view-draft-board-btn')?.addEventListener('click', () => this.showDraftBoard());
        // Auto-draft toggle button
        const autoDraftBtn = document.getElementById('auto-draft-toggle-btn');
        if (autoDraftBtn) {
            console.log('Auto-draft button found, setting up event listener');
            // Make sure button is not disabled
            autoDraftBtn.removeAttribute('disabled');
            autoDraftBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('Auto-draft button clicked!');
                this.toggleAutoDraft();
            });
        }
        else {
            console.error('Auto-draft button not found!');
        }
        // Recommended player button - show analysis modal
        document.getElementById('recommended-player-btn')?.addEventListener('click', () => this.showRecommendationAnalysis());
        // Close modal buttons
        document.getElementById('close-recommendation-modal')?.addEventListener('click', () => this.closeRecommendationModal());
        document.getElementById('recommendation-modal')?.addEventListener('click', (e) => {
            if (e.target.id === 'recommendation-modal') {
                this.closeRecommendationModal();
            }
        });
        document.getElementById('close-draft-board-modal')?.addEventListener('click', () => this.closeDraftBoardModal());
        document.getElementById('draft-board-modal')?.addEventListener('click', (e) => {
            if (e.target.id === 'draft-board-modal') {
                this.closeDraftBoardModal();
            }
        });
        // Search and filter
        document.getElementById('player-search')?.addEventListener('input', () => this.filterPlayers());
        document.getElementById('position-filter')?.addEventListener('change', () => this.filterPlayers());
    }
    async loadInitialState() {
        // Load players from master dictionary (auto-loaded on backend)
        try {
            this.allPlayers = await this.api.getAllPlayers();
            console.log(`✅ Loaded ${this.allPlayers.length} players from master dictionary`);
        }
        catch (error) {
            console.error('Error loading players:', error);
            // Continue anyway - players may load on next API call
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
        // Load auto-draft status
        try {
            const status = await this.api.getAutoDraftStatus();
            console.log('Loaded auto-draft status:', status);
            this.autoDraftEnabled = status.auto_draft_enabled;
            console.log('Setting autoDraftEnabled to:', this.autoDraftEnabled);
            this.updateAutoDraftButton();
        }
        catch (error) {
            console.error('Error loading auto-draft status:', error);
            // Default to false if status can't be loaded
            this.autoDraftEnabled = false;
            this.updateAutoDraftButton();
        }
        await this.refreshAll();
        this.showApp();
        // If draft is complete, show standings
        if (this.currentDraft?.is_complete) {
            await this.showStandings();
        }
    }
    async showStandings() {
        try {
            console.log('Loading standings...');
            const standingsData = await this.api.getStandings();
            console.log('Standings data received:', standingsData);
            if (standingsData.success && standingsData.standings) {
                this.renderer.renderStandings(standingsData);
            }
            else {
                alert('Failed to load standings. Make sure the draft has started and teams have players.');
            }
        }
        catch (error) {
            console.error('Error loading standings:', error);
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            alert('Error loading standings: ' + errorMessage);
        }
    }
    async trainMLModels() {
        // Confirm before training (takes time)
        const confirmed = confirm('Train AI Models?\n\n' +
            'This will analyze all player data to improve draft recommendations.\n' +
            '• Takes 1-2 minutes\n' +
            '• Only needed once (or when player data is updated)\n' +
            '• Models are saved and used automatically\n\n' +
            'Click OK to start training.');
        if (!confirmed) {
            return;
        }
        const btn = document.getElementById('train-ml-btn');
        if (btn) {
            btn.textContent = 'Training AI...';
            btn.setAttribute('disabled', 'true');
        }
        try {
            console.log('Training ML models...');
            const result = await this.api.trainMLModels();
            if (result.success) {
                let message = `✅ AI Models Trained Successfully!\n\n`;
                message += `Analyzed ${result.samples} players with ${result.features} features\n\n`;
                message += `Model Accuracy:\n`;
                message += `  • Test Accuracy: ${((result.ensemble_test_score || 0) * 100).toFixed(1)}%\n\n`;
                message += `The AI will now use these models to improve recommendations!\n\n`;
                message += `(Models are saved and will be used automatically)`;
                alert(message);
                console.log('ML models trained:', result);
            }
            else {
                alert('Failed to train models: ' + (result.message || 'Unknown error'));
            }
        }
        catch (error) {
            console.error('Error training ML models:', error);
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            alert('Error training AI models: ' + errorMessage);
        }
        finally {
            if (btn) {
                btn.textContent = 'Train AI Models';
                btn.removeAttribute('disabled');
            }
        }
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
    async restartDraft() {
        if (!confirm('Are you sure you want to clear all rosters? This will remove ALL players from ALL teams and reset all roster spots.')) {
            return;
        }
        try {
            const result = await this.api.restartDraft();
            if (result.draft) {
                this.currentDraft = result.draft;
            }
            else {
                this.currentDraft = null;
            }
            await this.refreshAll();
            alert(result.message || 'All team rosters cleared successfully!');
        }
        catch (error) {
            console.error('Error restarting draft:', error);
            alert('Error clearing rosters: ' + (error instanceof Error ? error.message : 'Unknown error'));
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
        // Get top recommendations
        let topRecommendation = null;
        try {
            const recommendations = await this.api.getRecommendations();
            if (recommendations && recommendations.length > 0) {
                topRecommendation = recommendations[0];
                this.currentRecommendation = topRecommendation; // Store for modal
                this.topRecommendations = recommendations.slice(0, 3); // Store top 3
            }
            else {
                this.currentRecommendation = null;
                this.topRecommendations = [];
            }
        }
        catch (error) {
            console.error('Error fetching recommendations:', error);
            this.currentRecommendation = null;
            this.topRecommendations = [];
        }
        this.renderer.updateDraftStatusBar(this.currentDraft, topRecommendation);
        // Check if auto-draft should trigger
        if (this.autoDraftEnabled) {
            await this.checkAndTriggerAutoDraft();
        }
    }
    async checkAndTriggerAutoDraft() {
        if (!this.currentDraft)
            return;
        // Don't auto-draft if draft is complete
        if (this.currentDraft.is_complete) {
            return;
        }
        // Determine whose turn it is
        const pickNumber = this.currentDraft.picks.length + 1;
        const round = Math.floor((pickNumber - 1) / this.currentDraft.total_teams) + 1;
        const pickInRound = ((pickNumber - 1) % this.currentDraft.total_teams) + 1;
        // Bob Uecker League: Rounds 1-4 no snake, Round 5+ snakes
        const teamOrder = [
            "Runtime Terror",
            "Dawg",
            "Long Balls",
            "Simba's Dublin Green Sox",
            "Young Guns",
            "Gashouse Gang",
            "Magnum GI",
            "Trex",
            "Like a Nightmare",
            "Big Sticks",
            "MAGA DOGE",
            "Guillotine",
            "Rieken Havoc"
        ];
        let currentTeam;
        if (round <= 4) {
            currentTeam = teamOrder[pickInRound - 1];
        }
        else {
            const snakeRound = round - 4; // Round 5 is snake round 1
            const isOddSnakeRound = snakeRound % 2 === 1;
            if (isOddSnakeRound) {
                currentTeam = teamOrder[this.currentDraft.total_teams - pickInRound];
            }
            else {
                currentTeam = teamOrder[pickInRound - 1];
            }
        }
        console.log(`Current team: ${currentTeam}, My team: ${this.currentDraft.my_team_name}, Auto-draft enabled: ${this.autoDraftEnabled}`);
        // Only auto-draft if it's not the user's team
        if (currentTeam !== this.currentDraft.my_team_name) {
            try {
                // Check if this team's roster is full
                const teamRosterSize = this.currentDraft.team_rosters[currentTeam]?.length || 0;
                if (teamRosterSize >= this.currentDraft.roster_size) {
                    // Team roster is full, skip auto-draft
                    console.log(`Skipping auto-draft for ${currentTeam} - roster is full (${teamRosterSize}/${this.currentDraft.roster_size})`);
                    return;
                }
                console.log(`Auto-drafting for ${currentTeam}...`);
                const result = await this.api.makeAutoDraftPick(currentTeam);
                this.currentDraft = result.draft;
                console.log(`✅ Auto-drafted ${result.picked_player.name} for ${currentTeam}. Reasoning: ${result.reasoning}`);
                // Check if draft is now complete
                if (result.draft_complete) {
                    console.log('Draft Complete! All roster spots filled.');
                    // Only refresh when draft completes
                    await this.refreshAll();
                }
                else {
                    // Don't refresh after auto-draft picks - just update draft state
                    // Only refresh when it's the user's turn or draft completes
                    const nextPickNumber = this.currentDraft.picks.length + 1;
                    const nextRound = Math.floor((nextPickNumber - 1) / this.currentDraft.total_teams) + 1;
                    const nextPickInRound = ((nextPickNumber - 1) % this.currentDraft.total_teams) + 1;
                    // Check if next pick is user's turn
                    const teamOrder = [
                        "Runtime Terror", "Dawg", "Long Balls", "Simba's Dublin Green Sox",
                        "Young Guns", "Gashouse Gang", "Magnum GI", "Trex",
                        "Like a Nightmare", "Big Sticks", "MAGA DOGE", "Guillotine", "Rieken Havoc"
                    ];
                    let nextTeam;
                    if (nextRound <= 4) {
                        nextTeam = teamOrder[nextPickInRound - 1];
                    }
                    else {
                        const nextSnakeRound = nextRound - 4;
                        const isNextOddSnakeRound = nextSnakeRound % 2 === 1;
                        if (isNextOddSnakeRound) {
                            nextTeam = teamOrder[this.currentDraft.total_teams - nextPickInRound];
                        }
                        else {
                            nextTeam = teamOrder[nextPickInRound - 1];
                        }
                    }
                    // Only refresh if it's now the user's turn
                    if (nextTeam === this.currentDraft.my_team_name) {
                        await this.refreshAll();
                    }
                }
                // If draft not complete, continue auto-drafting
                if (!result.draft_complete && this.autoDraftEnabled) {
                    setTimeout(() => this.checkAndTriggerAutoDraft(), 100);
                }
            }
            catch (error) {
                console.error('Error making auto-draft pick:', error);
                const errorMessage = error instanceof Error ? error.message : '';
                console.error('Error details:', errorMessage);
                // If error is about roster being full or draft complete, that's okay
                if (!errorMessage.includes('full') && !errorMessage.includes('complete')) {
                    // Log unexpected errors
                    alert(`Auto-draft error: ${errorMessage}`);
                }
            }
        }
        else {
            console.log(`Skipping auto-draft - it's ${this.currentDraft.my_team_name}'s turn (user's team)`);
        }
    }
    async toggleAutoDraft() {
        try {
            console.log('Toggle auto-draft clicked, current state:', this.autoDraftEnabled);
            const newState = !this.autoDraftEnabled;
            console.log('Setting auto-draft to:', newState);
            const result = await this.api.toggleAutoDraft(newState);
            console.log('Toggle result:', result);
            this.autoDraftEnabled = result.auto_draft_enabled;
            this.updateAutoDraftButton();
            if (this.autoDraftEnabled) {
                // Check if we should immediately trigger auto-draft
                console.log('Auto-draft enabled, triggering check...');
                await this.checkAndTriggerAutoDraft();
            }
            else {
                console.log('Auto-draft disabled');
            }
        }
        catch (error) {
            console.error('Error toggling auto-draft:', error);
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            alert(`Error toggling auto-draft: ${errorMessage}`);
        }
    }
    updateAutoDraftButton() {
        const btn = document.getElementById('auto-draft-toggle-btn');
        if (btn) {
            const text = `Auto-Draft: ${this.autoDraftEnabled ? 'ON' : 'OFF'}`;
            btn.textContent = text;
            console.log('Updated auto-draft button text to:', text);
            if (this.autoDraftEnabled) {
                btn.classList.add('btn-active');
            }
            else {
                btn.classList.remove('btn-active');
            }
        }
        else {
            console.error('Auto-draft button not found when trying to update!');
        }
    }
    async refreshAvailablePlayers() {
        try {
            const available = await this.api.getAvailablePlayers();
            console.log(`refreshAvailablePlayers: Got ${available.length} players`);
            const draftComplete = this.currentDraft?.is_complete || false;
            this.renderer.renderAvailablePlayers(available, (player) => this.draftPlayer(player), draftComplete);
            if (available.length === 0) {
                console.warn('No available players returned. This might indicate:');
                console.warn('  - No players loaded in the system');
                console.warn('  - All players have been drafted');
                console.warn('  - API error (check server logs)');
            }
        }
        catch (error) {
            console.error('Error refreshing available players:', error);
        }
    }
    async refreshMyTeam() {
        if (!this.currentDraft)
            return;
        const result = await this.api.getMyTeam();
        this.renderer.renderMyTeam(this.currentDraft.my_team_name, result.players, this.currentDraft, result.roster);
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
        // Note: We allow drafting even if draft is marked complete, as long as required positions aren't filled
        // The backend will check if the team can actually draft more players
        try {
            // If no draft exists, the backend will auto-create one
            const teamName = this.currentDraft?.my_team_name || 'Runtime Terror';
            const result = await this.api.makePick(player.player_id, teamName);
            this.currentDraft = result;
            // Check if draft is now complete
            if (result.is_complete) {
                console.log('Draft Complete! Showing standings...');
                await this.showStandings();
            }
            await this.refreshAll();
            // After user picks, check if auto-draft should trigger for next team
            if (this.autoDraftEnabled && !result.is_complete) {
                // Small delay to ensure state is updated
                setTimeout(() => this.checkAndTriggerAutoDraft(), 100);
            }
        }
        catch (error) {
            console.error('Error drafting player:', error);
            const errorMessage = error instanceof Error ? error.message : 'Error drafting player';
            alert(errorMessage);
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