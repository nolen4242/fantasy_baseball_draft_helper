import { Player, DraftState, Recommendation } from './types.js';

export class UIRenderer {
    updateDraftStatusBar(draft: DraftState, recommendation?: Recommendation | null): void {
        const currentPickEl = document.getElementById('current-pick-team');
        const currentRoundEl = document.getElementById('current-pick-round');
        const nextPickEl = document.getElementById('next-pick-team');
        const progressEl = document.getElementById('draft-progress-text');
        const recommendedPlayerEl = document.getElementById('recommended-player-name');
        const recommendedPositionEl = document.getElementById('recommended-player-position');

        if (!currentPickEl || !currentRoundEl || !nextPickEl || !progressEl) return;

        // Calculate whose turn it is using Bob Uecker League draft order
        const pickNumber = draft.picks.length + 1;
        const round = Math.floor((pickNumber - 1) / draft.total_teams) + 1;
        const pickInRound = ((pickNumber - 1) % draft.total_teams) + 1;
        
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
            // Rounds 1-5: standard order
            currentTeam = teamOrder[pickInRound - 1];
        } else {
            // Round 6+: snake draft
            const snakeRound = round - 5; // Round 6 is snake round 1
            const isOddSnakeRound = snakeRound % 2 === 1;
            if (isOddSnakeRound) {
                // Odd snake rounds: reverse order
                currentTeam = teamOrder[draft.total_teams - pickInRound];
            } else {
                // Even snake rounds: normal order
                currentTeam = teamOrder[pickInRound - 1];
            }
        }
        
        // Calculate next team
        const nextPickNumber = pickNumber + 1;
        const nextRound = Math.floor((nextPickNumber - 1) / draft.total_teams) + 1;
        const nextPickInRound = ((nextPickNumber - 1) % draft.total_teams) + 1;
        
        let nextTeam: string;
        if (nextRound <= 5) {
            nextTeam = teamOrder[nextPickInRound - 1];
        } else {
            const nextSnakeRound = nextRound - 5;
            const isNextOddSnakeRound = nextSnakeRound % 2 === 1;
            if (isNextOddSnakeRound) {
                nextTeam = teamOrder[draft.total_teams - nextPickInRound];
            } else {
                nextTeam = teamOrder[nextPickInRound - 1];
            }
        }

        currentPickEl.textContent = currentTeam;
        currentRoundEl.textContent = `Round ${round}, Pick ${pickInRound}`;
        nextPickEl.textContent = nextTeam;
        progressEl.textContent = `Pick ${pickNumber} of ${draft.total_teams * draft.roster_size}`;
        
        // Update recommended player
        if (recommendedPlayerEl && recommendedPositionEl) {
            if (recommendation && recommendation.player) {
                recommendedPlayerEl.textContent = recommendation.player.name;
                recommendedPositionEl.textContent = recommendation.player.position || '-';
            } else {
                recommendedPlayerEl.textContent = '-';
                recommendedPositionEl.textContent = '-';
            }
        }
    }

    renderAvailablePlayers(players: Player[], onDraft: (player: Player) => void): void {
        const container = document.getElementById('available-players-list');
        if (!container) return;

        const searchTerm = (document.getElementById('player-search') as HTMLInputElement)?.value.toLowerCase() || '';
        const positionFilter = (document.getElementById('position-filter') as HTMLSelectElement)?.value || '';

        const filtered = players.filter(p => {
            const matchesSearch = p.name.toLowerCase().includes(searchTerm) || 
                                 p.team.toLowerCase().includes(searchTerm);
            const matchesPosition = !positionFilter || p.position === positionFilter;
            return matchesSearch && matchesPosition;
        });

        container.innerHTML = filtered.map(player => this.renderPlayerCard(player, onDraft)).join('');
    }

    private renderPlayerCard(player: Player, onDraft: (player: Player) => void): string {
        const stats = this.getPlayerStats(player);
        const adpDisplay = player.adp ? `<span class="adp-badge">ADP: ${player.adp.toFixed(1)}</span>` : '';
        return `
            <div class="player-card" data-player-id="${player.player_id}">
                <div class="player-header">
                    <span class="player-name">${player.name}</span>
                    <div class="player-header-right">
                        ${adpDisplay}
                        <span class="player-position">${player.position || 'N/A'}</span>
                    </div>
                </div>
                <div class="player-team">${player.team}</div>
                <div class="player-stats">${stats}</div>
                <button class="draft-btn" onclick="window.draftPlayer('${player.player_id}')">Draft</button>
            </div>
        `;
    }

    renderMyTeam(teamName: string, players: Player[], draft: DraftState): void {
        const header = document.getElementById('my-team-name-header');
        const container = document.getElementById('my-team-roster');
        if (!container) return;

        if (header) header.textContent = teamName;

        // Bob Uecker League positions: 1 C, 1 1B, 1 2B, 1 3B, 1 SS, 1 MI, 1 CI, 4 OF, 1 U, 9 P
        const positions = [
            { pos: 'C', count: 1 },
            { pos: '1B', count: 1 },
            { pos: '2B', count: 1 },
            { pos: '3B', count: 1 },
            { pos: 'SS', count: 1 },
            { pos: 'MI', count: 1 },
            { pos: 'CI', count: 1 },
            { pos: 'OF', count: 4 },
            { pos: 'U', count: 1 },
            { pos: 'P', count: 9 }
        ];

        let html = '<div class="position-slots">';
        
        for (const { pos, count } of positions) {
            html += `<div class="position-group">
                <div class="position-label">${pos} (${count})</div>
                <div class="position-slots-container" data-position="${pos}">`;
            
            const positionPlayers = players.filter(p => this.playerFillsPosition(p, pos));
            for (let i = 0; i < count; i++) {
                const player = positionPlayers[i];
                if (player) {
                    html += `<div class="position-slot filled">
                        <div class="slot-player-name">${player.name}</div>
                        <div class="slot-player-team">${player.team}</div>
                    </div>`;
                } else {
                    html += `<div class="position-slot empty">Empty</div>`;
                }
            }
            
            html += `</div></div>`;
        }
        
        html += '</div>';
        container.innerHTML = html;
    }

    private playerFillsPosition(player: Player, position: string): boolean {
        if (position === 'MI') return player.position === '2B' || player.position === 'SS';
        if (position === 'CI') return player.position === '1B' || player.position === '3B';
        if (position === 'U') return !['SP', 'RP', 'P'].includes(player.position);
        if (position === 'P') return ['SP', 'RP', 'P'].includes(player.position);
        return player.position === position;
    }

    renderRecentPicks(picks: Array<{ pick: any; player: Player | null }>, onRevert?: (pickNumber: number) => void): void {
        const container = document.getElementById('recent-picks-list');
        if (!container) return;

        container.innerHTML = picks.map(({ pick, player }) => `
            <div class="pick-item">
                <div class="pick-header">
                    <span class="pick-round">R${pick.round}</span>
                    <span class="pick-number">#${pick.pick_number}</span>
                    ${onRevert ? `<button class="revert-btn" onclick="window.revertPick(${pick.pick_number})" title="Revert this pick">×</button>` : ''}
                </div>
                <div class="pick-team">${pick.team_name}</div>
                <div class="pick-player">${player ? player.name : pick.player_id}</div>
                <div class="pick-position">${player?.position || ''}</div>
            </div>
        `).join('');
    }

    renderOtherTeams(teams: Array<{ teamName: string; players: Player[] }>, onClick: (teamName: string) => void): void {
        const container = document.getElementById('other-teams-list');
        if (!container) return;

        container.innerHTML = teams.map(team => `
            <div class="team-card" data-team-name="${team.teamName}">
                <div class="team-name">${team.teamName}</div>
                <div class="team-player-count">${team.players.length} players</div>
                <div class="team-positions">
                    ${this.getTeamPositionSummary(team.players)}
                </div>
            </div>
        `).join('');

        // Attach click handlers
        teams.forEach(team => {
            const card = container.querySelector(`[data-team-name="${team.teamName}"]`);
            if (card) {
                card.addEventListener('click', () => onClick(team.teamName));
            }
        });
    }

    private getTeamPositionSummary(players: Player[]): string {
        const counts: { [pos: string]: number } = {};
        players.forEach(p => {
            counts[p.position] = (counts[p.position] || 0) + 1;
        });
        return Object.entries(counts)
            .map(([pos, count]) => `${pos}:${count}`)
            .join(' ');
    }

    private getPlayerStats(player: Player): string {
        const isHitter = !['SP', 'RP', 'P'].includes(player.position);
        const stats: string[] = [];

        if (isHitter) {
            if (player.projected_home_runs) stats.push(`HR: ${player.projected_home_runs}`);
            if (player.projected_obp) stats.push(`OBP: ${player.projected_obp.toFixed(3)}`);
            if (player.projected_runs) stats.push(`R: ${player.projected_runs}`);
            if (player.projected_rbi) stats.push(`RBI: ${player.projected_rbi}`);
            if (player.projected_stolen_bases) stats.push(`SB: ${player.projected_stolen_bases}`);
        } else {
            if (player.projected_wins) stats.push(`W: ${player.projected_wins}`);
            if (player.projected_quality_starts) stats.push(`QS: ${player.projected_quality_starts}`);
            if (player.projected_strikeouts) stats.push(`K: ${player.projected_strikeouts}`);
            if (player.projected_era) stats.push(`ERA: ${player.projected_era.toFixed(2)}`);
            if (player.projected_whip) stats.push(`WHIP: ${player.projected_whip.toFixed(2)}`);
            if (player.projected_saves) stats.push(`SV: ${player.projected_saves}`);
        }

        return stats.map(s => `<span class="stat">${s}</span>`).join('');
    }
}

