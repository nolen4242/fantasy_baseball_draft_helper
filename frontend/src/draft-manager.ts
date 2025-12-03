import { ApiClient } from './api.js';
import { UIRenderer } from './ui-renderer.js';
import { Player } from './types.js';

export class DraftManager {
    constructor(
        private api: ApiClient,
        private renderer: UIRenderer
    ) {
        // Expose methods to window for onclick handlers
        (window as any).draftPlayer = (playerId: string) => this.draftPlayerById(playerId);
        (window as any).showTeamDetails = (teamName: string) => this.showTeamDetails(teamName);
    }

    async draftPlayerById(playerId: string): Promise<void> {
        // Implementation will be handled by App class
        console.log('Draft player:', playerId);
    }

    async showTeamDetails(teamName: string): Promise<void> {
        // Implementation will be handled by App class
        console.log('Show team:', teamName);
    }
}

