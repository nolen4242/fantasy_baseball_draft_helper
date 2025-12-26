import { ApiClient } from './api.js';
export class UIRenderer {
    constructor(api) {
        this.api = api || new ApiClient();
    }
    updateDraftStatusBar(draft, recommendation) {
        const currentPickEl = document.getElementById('current-pick-team');
        const currentRoundEl = document.getElementById('current-pick-round');
        const nextPickEl = document.getElementById('next-pick-team');
        const progressEl = document.getElementById('draft-progress-text');
        const recommendedPlayerEl = document.getElementById('recommended-player-name');
        const recommendedPositionEl = document.getElementById('recommended-player-position');
        if (!currentPickEl || !currentRoundEl || !nextPickEl || !progressEl)
            return;
        // Check if draft is complete
        const isComplete = draft.is_complete || false;
        const totalPicks = draft.total_teams * draft.roster_size;
        const picksMade = draft.picks.length;
        // Calculate whose turn it is using Bob Uecker League draft order
        const pickNumber = draft.picks.length + 1;
        const round = Math.floor((pickNumber - 1) / draft.total_teams) + 1;
        const pickInRound = ((pickNumber - 1) % draft.total_teams) + 1;
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
            // Rounds 1-4: standard order (NO snake)
            currentTeam = teamOrder[pickInRound - 1];
        }
        else {
            // Round 5+: snake draft
            const snakeRound = round - 4; // Round 5 is snake round 1
            const isOddSnakeRound = snakeRound % 2 === 1;
            if (isOddSnakeRound) {
                // Odd snake rounds (5, 7, 9, etc.): reverse order
                currentTeam = teamOrder[draft.total_teams - pickInRound];
            }
            else {
                // Even snake rounds (6, 8, 10, etc.): normal order
                currentTeam = teamOrder[pickInRound - 1];
            }
        }
        // Calculate next team
        const nextPickNumber = pickNumber + 1;
        const nextRound = Math.floor((nextPickNumber - 1) / draft.total_teams) + 1;
        const nextPickInRound = ((nextPickNumber - 1) % draft.total_teams) + 1;
        let nextTeam;
        if (nextRound <= 4) {
            nextTeam = teamOrder[nextPickInRound - 1];
        }
        else {
            const nextSnakeRound = nextRound - 4;
            const isNextOddSnakeRound = nextSnakeRound % 2 === 1;
            if (isNextOddSnakeRound) {
                nextTeam = teamOrder[draft.total_teams - nextPickInRound];
            }
            else {
                nextTeam = teamOrder[nextPickInRound - 1];
            }
        }
        if (isComplete) {
            currentPickEl.textContent = 'DRAFT COMPLETE';
            currentRoundEl.textContent = `All ${totalPicks} picks made`;
            nextPickEl.textContent = '-';
            progressEl.textContent = `Draft Complete: ${picksMade}/${totalPicks} picks`;
            progressEl.style.color = '#32cd32';
            progressEl.style.fontWeight = '700';
        }
        else {
            currentPickEl.textContent = currentTeam;
            currentRoundEl.textContent = `Round ${round}, Pick ${pickInRound}`;
            nextPickEl.textContent = nextTeam;
            progressEl.textContent = `Pick ${pickNumber} of ${totalPicks}`;
            progressEl.style.color = '';
            progressEl.style.fontWeight = '';
        }
        // Update recommended player button
        const recommendedPlayerBtn = document.getElementById('recommended-player-btn');
        if (recommendedPlayerBtn && recommendedPlayerEl && recommendedPositionEl) {
            if (isComplete) {
                recommendedPlayerEl.textContent = 'Draft Complete';
                recommendedPositionEl.textContent = '-';
                recommendedPlayerBtn.setAttribute('disabled', 'true');
                recommendedPlayerBtn.style.cursor = 'not-allowed';
            }
            else if (recommendation && recommendation.player) {
                recommendedPlayerEl.textContent = recommendation.player.name;
                recommendedPositionEl.textContent = recommendation.player.position || '-';
                recommendedPlayerBtn.removeAttribute('disabled');
                recommendedPlayerBtn.style.cursor = 'pointer';
            }
            else {
                recommendedPlayerEl.textContent = '-';
                recommendedPositionEl.textContent = '-';
                recommendedPlayerBtn.setAttribute('disabled', 'true');
                recommendedPlayerBtn.style.cursor = 'not-allowed';
            }
        }
    }
    renderAvailablePlayers(players, onDraft, draftComplete = false) {
        const container = document.getElementById('available-players-list');
        if (!container)
            return;
        if (draftComplete) {
            container.innerHTML = '<div style="padding: 20px; text-align: center; color: #32cd32; font-weight: 700;">Draft Complete - All Roster Spots Filled</div>';
            return;
        }
        const searchTerm = document.getElementById('player-search')?.value.toLowerCase() || '';
        const positionFilter = document.getElementById('position-filter')?.value || '';
        const filtered = players.filter(p => {
            const matchesSearch = p.name.toLowerCase().includes(searchTerm) ||
                p.team.toLowerCase().includes(searchTerm);
            const matchesPosition = !positionFilter || p.position === positionFilter;
            return matchesSearch && matchesPosition;
        });
        container.innerHTML = filtered.map(player => this.renderPlayerCard(player, onDraft, draftComplete)).join('');
    }
    renderPlayerCard(player, onDraft, draftComplete = false) {
        const stats = this.getPlayerStats(player);
        const adpDisplay = player.adp ? `<span class="adp-badge">ADP: ${player.adp.toFixed(1)}</span>` : '';
        const draftButtonDisabled = draftComplete ? 'disabled' : '';
        const draftButtonClass = draftComplete ? 'draft-btn draft-btn-disabled' : 'draft-btn';
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
                <button class="${draftButtonClass}" onclick="window.draftPlayer('${player.player_id}')" ${draftButtonDisabled}>${draftComplete ? 'Draft Complete' : 'Draft'}</button>
            </div>
        `;
    }
    renderMyTeam(teamName, players, draft, roster = null) {
        const header = document.getElementById('my-team-name-header');
        const container = document.getElementById('my-team-roster');
        if (!container)
            return;
        if (header)
            header.textContent = teamName;
        // Bob Uecker League positions: 1 C, 1 1B, 1 2B, 1 3B, 1 SS, 1 MI, 1 CI, 4 OF, 1 U, 9 P, 1 BENCH
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
            { pos: 'P', count: 9 },
            { pos: 'BENCH', count: 1 }
        ];
        let html = '<div class="position-slots">';
        // Use roster structure if available, otherwise fall back to old logic
        const rosterPositions = roster?.positions || {};
        const hasRosterData = roster && Object.keys(rosterPositions).length > 0;
        // If no roster data, build a simple mapping from players
        let playerPositionMap = {};
        if (!hasRosterData && players.length > 0) {
            // Fallback: group players by their primary position
            for (const player of players) {
                const pos = player.position;
                if (!playerPositionMap[pos]) {
                    playerPositionMap[pos] = [];
                }
                playerPositionMap[pos].push(player);
            }
        }
        for (const { pos, count } of positions) {
            html += `<div class="position-group">
                <div class="position-label">${pos} (${count})</div>
                <div class="position-slots-container" data-position="${pos}">`;
            const positionSlots = rosterPositions[pos] || [];
            for (let i = 0; i < count; i++) {
                const slotPlayer = positionSlots[i];
                if (slotPlayer && slotPlayer.player_id) {
                    // Player is assigned to this slot from roster
                    html += `<div class="position-slot filled draggable" 
                        draggable="true"
                        data-player-id="${slotPlayer.player_id}"
                        data-position="${pos}"
                        data-index="${i}">
                        <div class="slot-player-name">${slotPlayer.name}</div>
                        <div class="slot-player-team">${slotPlayer.team}</div>
                    </div>`;
                }
                else if (!hasRosterData) {
                    // Fallback: show players by position if roster not available
                    const posPlayers = playerPositionMap[pos] || [];
                    const player = posPlayers[i];
                    if (player && this.playerFillsPosition(player, pos)) {
                        html += `<div class="position-slot filled draggable" 
                            draggable="true"
                            data-player-id="${player.player_id}"
                            data-position="${pos}"
                            data-index="${i}">
                            <div class="slot-player-name">${player.name}</div>
                            <div class="slot-player-team">${player.team}</div>
                        </div>`;
                    }
                    else {
                        // Empty slot - can be drop target
                        html += `<div class="position-slot empty droppable" 
                            data-position="${pos}"
                            data-index="${i}">Empty</div>`;
                    }
                }
                else {
                    // Empty slot - can be drop target
                    html += `<div class="position-slot empty droppable" 
                        data-position="${pos}"
                        data-index="${i}">Empty</div>`;
                }
            }
            html += `</div></div>`;
        }
        html += '</div>';
        container.innerHTML = html;
        // Set up drag and drop
        this.setupDragAndDrop(container, draft.my_team_name);
    }
    setupDragAndDrop(container, teamName) {
        let draggedElement = null;
        let draggedData = null;
        // Get all draggable and droppable elements
        const draggables = container.querySelectorAll('.draggable');
        const droppables = container.querySelectorAll('.droppable');
        // Drag start
        draggables.forEach(draggable => {
            draggable.addEventListener('dragstart', (e) => {
                const dragEvent = e;
                const target = dragEvent.target;
                draggedElement = target;
                draggedData = {
                    playerId: target.dataset.playerId || '',
                    position: target.dataset.position || '',
                    index: parseInt(target.dataset.index || '0')
                };
                target.style.opacity = '0.5';
                if (dragEvent.dataTransfer) {
                    dragEvent.dataTransfer.effectAllowed = 'move';
                }
            });
        });
        // Drag end
        draggables.forEach(draggable => {
            draggable.addEventListener('dragend', (e) => {
                if (draggedElement) {
                    draggedElement.style.opacity = '1';
                    draggedElement = null;
                }
                // Remove drag-over class from all droppables
                droppables.forEach(drop => drop.classList.remove('drag-over'));
            });
        });
        // Drag over - allow drop
        droppables.forEach(droppable => {
            droppable.addEventListener('dragover', (e) => {
                const dragEvent = e;
                dragEvent.preventDefault();
                if (draggedData) {
                    if (dragEvent.dataTransfer) {
                        dragEvent.dataTransfer.dropEffect = 'move';
                    }
                    droppable.classList.add('drag-over');
                }
            });
        });
        // Drag leave
        droppables.forEach(droppable => {
            droppable.addEventListener('dragleave', (e) => {
                droppable.classList.remove('drag-over');
            });
        });
        // Drop
        droppables.forEach(droppable => {
            droppable.addEventListener('drop', async (e) => {
                const dragEvent = e;
                dragEvent.preventDefault();
                const droppableEl = droppable;
                droppableEl.classList.remove('drag-over');
                if (draggedData) {
                    const toPosition = droppableEl.dataset.position || '';
                    const toIndex = parseInt(droppableEl.dataset.index || '0');
                    // Call API to move player
                    try {
                        await this.api.movePlayerPosition(draggedData.playerId, draggedData.position, draggedData.index, toPosition, toIndex, teamName);
                        // Trigger custom event to refresh
                        window.dispatchEvent(new CustomEvent('playerMoved', {
                            detail: { teamName }
                        }));
                    }
                    catch (error) {
                        console.error('Error moving player:', error);
                        alert('Failed to move player: ' + (error instanceof Error ? error.message : 'Unknown error'));
                    }
                }
                draggedData = null;
            });
        });
    }
    playerFillsPosition(player, position) {
        if (position === 'MI')
            return player.position === '2B' || player.position === 'SS';
        if (position === 'CI')
            return player.position === '1B' || player.position === '3B';
        if (position === 'U')
            return !['SP', 'RP', 'P'].includes(player.position);
        if (position === 'P')
            return ['SP', 'RP', 'P'].includes(player.position);
        return player.position === position;
    }
    renderRecentPicks(picks, onRevert) {
        const container = document.getElementById('recent-picks-list');
        if (!container)
            return;
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
    renderOtherTeams(teams, onClick) {
        const container = document.getElementById('other-teams-list');
        if (!container)
            return;
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
    getTeamPositionSummary(players) {
        const counts = {};
        players.forEach(p => {
            counts[p.position] = (counts[p.position] || 0) + 1;
        });
        return Object.entries(counts)
            .map(([pos, count]) => `${pos}:${count}`)
            .join(' ');
    }
    getPlayerStats(player) {
        const isHitter = !['SP', 'RP', 'P'].includes(player.position);
        const stats = [];
        if (isHitter) {
            if (player.projected_home_runs)
                stats.push(`HR: ${player.projected_home_runs}`);
            if (player.projected_obp)
                stats.push(`OBP: ${player.projected_obp.toFixed(3)}`);
            if (player.projected_runs)
                stats.push(`R: ${player.projected_runs}`);
            if (player.projected_rbi)
                stats.push(`RBI: ${player.projected_rbi}`);
            if (player.projected_stolen_bases)
                stats.push(`SB: ${player.projected_stolen_bases}`);
        }
        else {
            if (player.projected_wins)
                stats.push(`W: ${player.projected_wins}`);
            if (player.projected_quality_starts)
                stats.push(`QS: ${player.projected_quality_starts}`);
            if (player.projected_strikeouts)
                stats.push(`K: ${player.projected_strikeouts}`);
            if (player.projected_era)
                stats.push(`ERA: ${player.projected_era.toFixed(2)}`);
            if (player.projected_whip)
                stats.push(`WHIP: ${player.projected_whip.toFixed(2)}`);
            if (player.projected_saves)
                stats.push(`SV: ${player.projected_saves}`);
        }
        return stats.map(s => `<span class="stat">${s}</span>`).join('');
    }
    renderStandings(standingsData) {
        console.log('Rendering standings:', standingsData);
        // Create or get standings container
        let standingsContainer = document.getElementById('standings-container');
        if (!standingsContainer) {
            standingsContainer = document.createElement('div');
            standingsContainer.id = 'standings-container';
            standingsContainer.className = 'standings-container';
            document.body.appendChild(standingsContainer);
        }
        if (!standingsData.standings || standingsData.standings.length === 0) {
            standingsContainer.innerHTML = `
                <div class="standings-header">
                    <h2>📊 Projected Standings</h2>
                    <button id="close-standings-btn" class="btn-small">Close</button>
                </div>
                <div style="padding: 20px; color: white;">
                    <p>No standings data available. Make sure the draft has started and teams have players.</p>
                </div>
            `;
            standingsContainer.style.display = 'block';
            document.getElementById('close-standings-btn')?.addEventListener('click', () => {
                standingsContainer.style.display = 'none';
            });
            return;
        }
        const battingCats = standingsData.categories.batting;
        const pitchingCats = standingsData.categories.pitching;
        const allCats = [...battingCats, ...pitchingCats];
        // Build standings HTML
        let html = `
            <div class="standings-header">
                <h2>📊 Projected Standings</h2>
                <button id="close-standings-btn" class="btn-small">Close</button>
            </div>
            <div class="standings-table-wrapper">
                <table class="standings-table">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Team</th>
                            <th>Points</th>
                            ${allCats.map(cat => `<th>${cat}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
        `;
        for (const team of standingsData.standings) {
            const rankClass = team.rank <= 3 ? 'top-rank' : '';
            html += `
                <tr class="${rankClass}">
                    <td class="rank-cell">${team.rank}</td>
                    <td class="team-name-cell">${team.team_name}</td>
                    <td class="points-cell"><strong>${team.total_points}</strong></td>
            `;
            // Add category data
            for (const cat of allCats) {
                const total = team.category_totals[cat] || 0;
                const rank = team.category_ranks[cat] || 0;
                const isLowerBetter = cat === 'ERA' || cat === 'WHIP';
                const rankClass = rank === 1 ? 'rank-1' : rank <= 3 ? 'rank-top-3' : '';
                let displayValue = '';
                if (cat === 'OBP') {
                    displayValue = total.toFixed(3);
                }
                else if (cat === 'ERA' || cat === 'WHIP') {
                    displayValue = total.toFixed(2);
                }
                else {
                    displayValue = total.toFixed(1);
                }
                html += `
                    <td class="category-cell ${rankClass}" title="Rank: ${rank}">
                        <div class="category-value">${displayValue}</div>
                        <div class="category-rank">(${rank})</div>
                    </td>
                `;
            }
            html += `</tr>`;
        }
        html += `
                    </tbody>
                </table>
            </div>
        `;
        standingsContainer.innerHTML = html;
        standingsContainer.style.display = 'block';
        // Add close button handler
        document.getElementById('close-standings-btn')?.addEventListener('click', () => {
            standingsContainer.style.display = 'none';
        });
    }
}
//# sourceMappingURL=ui-renderer.js.map