export class DraftManager {
    constructor(api, renderer) {
        this.api = api;
        this.renderer = renderer;
        // Expose methods to window for onclick handlers
        window.draftPlayer = (playerId) => this.draftPlayerById(playerId);
        window.showTeamDetails = (teamName) => this.showTeamDetails(teamName);
    }
    async draftPlayerById(playerId) {
        // Implementation will be handled by App class
        console.log('Draft player:', playerId);
    }
    async showTeamDetails(teamName) {
        // Implementation will be handled by App class
        console.log('Show team:', teamName);
    }
}
//# sourceMappingURL=draft-manager.js.map