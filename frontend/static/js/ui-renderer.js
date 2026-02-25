import { ApiClient } from './api.js';
export class UIRenderer {
    constructor(api) {
        this.api = api || new ApiClient();
    }
    // ── Position Eligibility Helpers ─────────────────
    getEligiblePositions(position) {
        const map = {
            'C': ['C', 'U', 'BENCH'],
            '1B': ['1B', 'CI', 'U', 'BENCH'],
            '2B': ['2B', 'MI', 'U', 'BENCH'],
            '3B': ['3B', 'CI', 'U', 'BENCH'],
            'SS': ['SS', 'MI', 'U', 'BENCH'],
            'OF': ['OF', 'U', 'BENCH'],
            'SP': ['P', 'BENCH'],
            'RP': ['P', 'BENCH'],
            'P': ['P', 'BENCH'],
        };
        return map[position] || [position, 'BENCH'];
    }
    renderEligibilityBadges(position) {
        const eligible = this.getEligiblePositions(position);
        return `<div class="eligibility-badges">${eligible.map(p => `<span class="elig-badge">${p}</span>`).join('')}</div>`;
    }
    // ── Category Need Dots ──────────────────────────
    renderCategoryDots(player, categoryNeeds) {
        if (!categoryNeeds || categoryNeeds.length === 0)
            return '';
        const isHitter = !['SP', 'RP', 'P'].includes(player.position);
        const hitterCats = ['HR', 'OBP', 'R', 'RBI', 'SB'];
        const pitcherCats = ['ERA', 'K', 'SHOLDS', 'WHIP', 'WQS'];
        const relevantCats = isHitter ? hitterCats : pitcherCats;
        const dots = categoryNeeds
            .filter(cn => relevantCats.includes(cn.category) && (cn.need === 'critical' || cn.need === 'moderate'))
            .map(cn => {
            const cls = cn.need === 'critical' ? 'cat-dot-critical' : 'cat-dot-moderate';
            return `<span class="cat-dot ${cls}" title="${cn.category}: ${cn.need}">${cn.category}</span>`;
        });
        if (dots.length === 0)
            return '';
        return `<div class="category-dots">${dots.join('')}</div>`;
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
        let currentTeam;
        if (round <= 5) {
            // Rounds 1-5: standard order
            currentTeam = teamOrder[pickInRound - 1];
        }
        else {
            // Round 6+: snake draft
            const snakeRound = round - 5; // Round 6 is snake round 1
            const isOddSnakeRound = snakeRound % 2 === 1;
            if (isOddSnakeRound) {
                // Odd snake rounds: reverse order
                currentTeam = teamOrder[draft.total_teams - pickInRound];
            }
            else {
                // Even snake rounds: normal order
                currentTeam = teamOrder[pickInRound - 1];
            }
        }
        // Calculate next team
        const nextPickNumber = pickNumber + 1;
        const nextRound = Math.floor((nextPickNumber - 1) / draft.total_teams) + 1;
        const nextPickInRound = ((nextPickNumber - 1) % draft.total_teams) + 1;
        let nextTeam;
        if (nextRound <= 5) {
            nextTeam = teamOrder[nextPickInRound - 1];
        }
        else {
            const nextSnakeRound = nextRound - 5;
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
            progressEl.style.color = '#157145';
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
        // Update recommended player
        if (recommendedPlayerEl && recommendedPositionEl) {
            if (isComplete) {
                recommendedPlayerEl.textContent = 'Draft Complete';
                recommendedPlayerEl.style.cursor = 'default';
                recommendedPlayerEl.onclick = null;
                recommendedPositionEl.textContent = '-';
            }
            else if (recommendation && recommendation.player) {
                recommendedPlayerEl.textContent = recommendation.player.name;
                recommendedPlayerEl.style.cursor = 'pointer';
                recommendedPlayerEl.onclick = () => {
                    window.showPlayerDetails(recommendation.player.player_id);
                };
                recommendedPositionEl.textContent = recommendation.player.position || '-';
            }
            else {
                recommendedPlayerEl.textContent = '-';
                recommendedPlayerEl.style.cursor = 'default';
                recommendedPlayerEl.onclick = null;
                recommendedPositionEl.textContent = '-';
            }
        }
    }
    renderAvailablePlayers(players, onDraft, draftComplete = false, categoryNeeds = null, compareSelection = []) {
        const container = document.getElementById('available-players-list');
        if (!container)
            return;
        if (draftComplete) {
            container.innerHTML = '<div style="padding: 20px; text-align: center; color: #157145; font-weight: 700;">Draft Complete - All Roster Spots Filled</div>';
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
        container.innerHTML = filtered.map(player => this.renderPlayerCard(player, onDraft, draftComplete, categoryNeeds, compareSelection)).join('');
    }
    renderPlayerCard(player, onDraft, draftComplete = false, categoryNeeds = null, compareSelection = []) {
        const stats = this.getPlayerStats(player);
        const adpDisplay = player.adp ? `<span class="adp-badge">ADP: ${player.adp.toFixed(1)}</span>` : '';
        const draftButtonDisabled = draftComplete ? 'disabled' : '';
        const draftButtonClass = draftComplete ? 'draft-btn draft-btn-disabled' : 'draft-btn';
        const eligBadges = this.renderEligibilityBadges(player.position);
        const catDots = this.renderCategoryDots(player, categoryNeeds);
        const isChecked = compareSelection.includes(player.player_id) ? 'checked' : '';
        return `
            <div class="player-card" data-player-id="${player.player_id}" onclick="window.showPlayerDetails('${player.player_id}')">
                <div class="player-header">
                    <span class="player-name">${player.name}</span>
                    <div class="player-header-right">
                        ${adpDisplay}
                        <span class="player-position">${player.position || 'N/A'}</span>
                    </div>
                </div>
                ${eligBadges}
                <div class="player-team">${player.team}</div>
                ${catDots}
                <div class="player-stats">${stats}</div>
                <div class="player-card-actions">
                    <label class="compare-check" onclick="event.stopPropagation()">
                        <input type="checkbox" ${isChecked} onchange="window.toggleCompare('${player.player_id}')" /> Compare
                    </label>
                    <button class="${draftButtonClass}" onclick="event.stopPropagation(); window.draftPlayer('${player.player_id}')" ${draftButtonDisabled}>${draftComplete ? 'Draft Complete' : 'Draft'}</button>
                </div>
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
                    <div class="pick-actions">
                        ${onRevert ? `<button class="batch-revert-btn" onclick="window.batchRevertTo(${pick.pick_number})" title="Revert all picks back to here">Revert to here</button>` : ''}
                        ${onRevert ? `<button class="revert-btn" onclick="window.revertPick(${pick.pick_number})" title="Revert this pick">×</button>` : ''}
                    </div>
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
    renderStandings(data, myTeam) {
        const container = document.getElementById('standings-content');
        if (!container)
            return;
        const battingCats = ['HR', 'OBP', 'R', 'RBI', 'SB'];
        const pitchingCats = ['ERA', 'K', 'SHOLDS', 'WHIP', 'WQS'];
        const allCats = [...battingCats, ...pitchingCats];
        const numTeams = data.final_rankings.length;
        const leader = data.final_rankings[0];
        const leaderPts = data.total_points[leader] ?? 0;
        let html = '<table class="standings-table"><thead><tr>';
        html += '<th>Rank</th><th>Team</th><th>Bat</th><th>Pitch</th><th>Total</th><th>Behind</th>';
        for (const cat of allCats)
            html += `<th>${cat}</th>`;
        html += '</tr></thead><tbody>';
        for (let i = 0; i < data.final_rankings.length; i++) {
            const team = data.final_rankings[i];
            const isMyTeam = team === myTeam;
            const rowClass = isMyTeam ? 'standings-row-mine' : '';
            const bat = data.batting_points[team] ?? 0;
            const pitch = data.pitching_points[team] ?? 0;
            const total = data.total_points[team] ?? 0;
            const behind = i === 0 ? 0 : leaderPts - total;
            html += `<tr class="${rowClass}">`;
            html += `<td>${i + 1}</td><td>${team}</td>`;
            html += `<td>${bat % 1 ? bat.toFixed(1) : bat}</td>`;
            html += `<td>${pitch % 1 ? pitch.toFixed(1) : pitch}</td>`;
            html += `<td class="standings-total">${total % 1 ? total.toFixed(1) : total}</td>`;
            html += `<td>${behind % 1 ? behind.toFixed(1) : behind}</td>`;
            for (const cat of allCats) {
                const pts = data.category_points[cat]?.[team] ?? 0;
                const ptsStr = pts % 1 ? pts.toFixed(1) : String(pts);
                const cls = pts >= numTeams - 2 ? 'cat-top' : pts <= 3 ? 'cat-bot' : '';
                const rawVal = data.category_totals[team]?.[cat] ?? 0;
                html += `<td class="${cls}" title="${rawVal.toFixed(3)}">${ptsStr}</td>`;
            }
            html += '</tr>';
        }
        html += '</tbody></table>';
        container.innerHTML = html;
    }
    renderDraftBoard(data, teams, myTeam) {
        const container = document.getElementById('draftboard-content');
        if (!container)
            return;
        let html = '<div class="draftboard-scroll"><table class="draftboard-table"><thead><tr><th>Rd</th>';
        for (const t of teams) {
            const cls = t === myTeam ? 'db-mine' : '';
            const short = t.length > 12 ? t.substring(0, 11) + '…' : t;
            html += `<th class="${cls}">${short}</th>`;
        }
        html += '</tr></thead><tbody>';
        const picksByRound = {};
        for (const p of data.board) {
            if (!picksByRound[p.round])
                picksByRound[p.round] = {};
            picksByRound[p.round][p.team_name] = { player_name: p.player_name, position: p.position };
        }
        for (let r = 1; r <= data.roster_size; r++) {
            html += `<tr><td class="db-round">${r}</td>`;
            for (const t of teams) {
                const pick = picksByRound[r]?.[t];
                const cls = t === myTeam ? 'db-mine-cell' : '';
                if (pick) {
                    html += `<td class="${cls}"><span class="db-name">${pick.player_name}</span><span class="db-pos">${pick.position}</span></td>`;
                }
                else {
                    html += `<td class="${cls} db-empty">—</td>`;
                }
            }
            html += '</tr>';
        }
        html += '</tbody></table></div>';
        container.innerHTML = html;
    }
    // ── Feature 1: Player Detail Modal ──────────────
    renderPlayerModal(player, onDraft, draftComplete) {
        let existing = document.getElementById('player-detail-modal');
        if (existing)
            existing.remove();
        const isHitter = !['SP', 'RP', 'P'].includes(player.position);
        const adpDisplay = player.adp ? `<span class="adp-badge">ADP: ${player.adp.toFixed(1)}</span>` : '';
        const eligBadges = this.renderEligibilityBadges(player.position);
        let statsHtml = '';
        if (isHitter) {
            statsHtml = `
                <tr><td>HR</td><td>${player.projected_home_runs ?? '-'}</td></tr>
                <tr><td>OBP</td><td>${player.projected_obp != null ? player.projected_obp.toFixed(3) : '-'}</td></tr>
                <tr><td>R</td><td>${player.projected_runs ?? '-'}</td></tr>
                <tr><td>RBI</td><td>${player.projected_rbi ?? '-'}</td></tr>
                <tr><td>SB</td><td>${player.projected_stolen_bases ?? '-'}</td></tr>`;
        }
        else {
            statsHtml = `
                <tr><td>W</td><td>${player.projected_wins ?? '-'}</td></tr>
                <tr><td>QS</td><td>${player.projected_quality_starts ?? '-'}</td></tr>
                <tr><td>K</td><td>${player.projected_strikeouts ?? '-'}</td></tr>
                <tr><td>ERA</td><td>${player.projected_era != null ? player.projected_era.toFixed(2) : '-'}</td></tr>
                <tr><td>WHIP</td><td>${player.projected_whip != null ? player.projected_whip.toFixed(2) : '-'}</td></tr>
                <tr><td>SV</td><td>${player.projected_saves ?? '-'}</td></tr>
                <tr><td>HD</td><td>${player.projected_holds ?? '-'}</td></tr>`;
        }
        const draftBtnClass = draftComplete ? 'btn-primary draft-btn-disabled' : 'btn-primary';
        const draftBtnDisabled = draftComplete ? 'disabled' : '';
        const modal = document.createElement('div');
        modal.id = 'player-detail-modal';
        modal.className = 'modal';
        modal.onclick = (e) => { if (e.target === modal)
            window.closePlayerModal(); };
        modal.innerHTML = `
            <div class="modal-content player-modal-content">
                <button class="modal-close-btn" onclick="window.closePlayerModal()">×</button>
                <div class="player-modal-header">
                    <h2>${player.name}</h2>
                    <div class="player-modal-meta">
                        <span class="player-position">${player.position}</span>
                        ${adpDisplay}
                        <span class="player-modal-team">${player.team}</span>
                    </div>
                    ${eligBadges}
                </div>
                <table class="player-modal-stats">
                    <thead><tr><th>Stat</th><th>Projected</th></tr></thead>
                    <tbody>${statsHtml}</tbody>
                </table>
                <button class="${draftBtnClass}" onclick="window.draftPlayer('${player.player_id}'); window.closePlayerModal();" ${draftBtnDisabled}>
                    ${draftComplete ? 'Draft Complete' : `Draft ${player.name}`}
                </button>
            </div>
        `;
        document.body.appendChild(modal);
    }
    // ── Feature 4: Comparison Modal ─────────────────
    renderCompareModal(players) {
        let existing = document.getElementById('compare-modal');
        if (existing)
            existing.remove();
        const allHitters = players.every(p => !['SP', 'RP', 'P'].includes(p.position));
        const allPitchers = players.every(p => ['SP', 'RP', 'P'].includes(p.position));
        let statDefs = [];
        if (allHitters) {
            statDefs = [
                { label: 'HR', key: 'projected_home_runs' },
                { label: 'OBP', key: 'projected_obp', format: (v) => v.toFixed(3) },
                { label: 'R', key: 'projected_runs' },
                { label: 'RBI', key: 'projected_rbi' },
                { label: 'SB', key: 'projected_stolen_bases' },
            ];
        }
        else if (allPitchers) {
            statDefs = [
                { label: 'W', key: 'projected_wins' },
                { label: 'QS', key: 'projected_quality_starts' },
                { label: 'K', key: 'projected_strikeouts' },
                { label: 'ERA', key: 'projected_era', format: (v) => v.toFixed(2), lower: true },
                { label: 'WHIP', key: 'projected_whip', format: (v) => v.toFixed(2), lower: true },
                { label: 'SV', key: 'projected_saves' },
                { label: 'HD', key: 'projected_holds' },
            ];
        }
        else {
            statDefs = [
                { label: 'HR', key: 'projected_home_runs' },
                { label: 'OBP', key: 'projected_obp', format: (v) => v.toFixed(3) },
                { label: 'R', key: 'projected_runs' },
                { label: 'RBI', key: 'projected_rbi' },
                { label: 'SB', key: 'projected_stolen_bases' },
                { label: 'W', key: 'projected_wins' },
                { label: 'K', key: 'projected_strikeouts' },
                { label: 'ERA', key: 'projected_era', format: (v) => v.toFixed(2), lower: true },
                { label: 'WHIP', key: 'projected_whip', format: (v) => v.toFixed(2), lower: true },
            ];
        }
        let headerCols = '<th>Stat</th>' + players.map(p => `<th>${p.name}</th>`).join('');
        let rows = statDefs.map(sd => {
            const vals = players.map(p => p[sd.key]);
            const numericVals = vals.filter((v) => v != null);
            const best = numericVals.length > 0 ? (sd.lower ? Math.min(...numericVals) : Math.max(...numericVals)) : null;
            const cells = vals.map(v => {
                if (v == null)
                    return '<td>-</td>';
                const formatted = sd.format ? sd.format(v) : String(v);
                const isBest = best !== null && v === best;
                return `<td class="${isBest ? 'compare-best' : ''}">${formatted}</td>`;
            }).join('');
            return `<tr><td>${sd.label}</td>${cells}</tr>`;
        }).join('');
        const modal = document.createElement('div');
        modal.id = 'compare-modal';
        modal.className = 'modal';
        modal.onclick = (e) => { if (e.target === modal)
            modal.remove(); };
        modal.innerHTML = `
            <div class="modal-content compare-modal-content">
                <button class="modal-close-btn" onclick="document.getElementById('compare-modal')?.remove()">×</button>
                <h2>Player Comparison</h2>
                <table class="compare-table">
                    <thead><tr>${headerCols}</tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
        document.body.appendChild(modal);
    }
    // ── Feature 7: Projected Standings Chart ────────
    renderStandingsChart(data, myTeam) {
        const container = document.getElementById('chart-content');
        if (!container)
            return;
        if (!data.final_rankings || data.final_rankings.length === 0) {
            container.innerHTML = '<p class="muted-text">Draft some players to see chart…</p>';
            return;
        }
        const teams = data.final_rankings;
        const maxPts = Math.max(...teams.map(t => data.total_points[t] || 0), 1);
        const svgW = 800;
        const svgH = 300;
        const barW = Math.floor((svgW - 40) / teams.length) - 4;
        const chartH = svgH - 50;
        let bars = '';
        teams.forEach((t, i) => {
            const pts = data.total_points[t] || 0;
            const barH = Math.max((pts / maxPts) * chartH, 2);
            const x = 30 + i * (barW + 4);
            const y = chartH - barH + 10;
            const fill = t === myTeam ? 'var(--turf-green)' : 'var(--air-force-blue)';
            const shortName = t.length > 8 ? t.substring(0, 7) + '…' : t;
            bars += `<rect x="${x}" y="${y}" width="${barW}" height="${barH}" fill="${fill}" rx="3"/>`;
            bars += `<text x="${x + barW / 2}" y="${y - 4}" text-anchor="middle" font-size="9" fill="var(--text-primary)">${pts % 1 ? pts.toFixed(1) : pts}</text>`;
            bars += `<text x="${x + barW / 2}" y="${svgH - 5}" text-anchor="middle" font-size="8" fill="var(--text-muted)" transform="rotate(-45 ${x + barW / 2} ${svgH - 5})">${shortName}</text>`;
        });
        container.innerHTML = `
            <svg viewBox="0 0 ${svgW} ${svgH}" class="standings-chart-svg">
                <line x1="28" y1="10" x2="28" y2="${chartH + 10}" stroke="var(--border-medium)" stroke-width="1"/>
                <line x1="28" y1="${chartH + 10}" x2="${svgW}" y2="${chartH + 10}" stroke="var(--border-medium)" stroke-width="1"/>
                ${bars}
            </svg>
        `;
    }
    // ── Feature 8: Trade Analyzer ───────────────────
    renderTradeAnalyzer(myTeam, teams, myPlayers, draft, allPlayers) {
        const container = document.getElementById('trade-content');
        if (!container)
            return;
        const otherTeams = teams.filter(t => t !== myTeam);
        const teamOptions = otherTeams.map(t => `<option value="${t}">${t}</option>`).join('');
        container.innerHTML = `
            <div class="trade-analyzer">
                <div class="trade-teams-row">
                    <div class="trade-team-col">
                        <h3>${myTeam}</h3>
                        <select id="trade-players-a" multiple class="trade-player-select">
                            ${myPlayers.map(p => `<option value="${p.player_id}">${p.name} (${p.position})</option>`).join('')}
                        </select>
                    </div>
                    <div class="trade-team-col">
                        <h3>Trade Partner</h3>
                        <select id="trade-team-b" class="trade-team-select" onchange="window.updateTradeBPlayers()">
                            <option value="">Select team…</option>
                            ${teamOptions}
                        </select>
                        <select id="trade-players-b" multiple class="trade-player-select">
                        </select>
                    </div>
                </div>
                <button class="btn-primary trade-analyze-btn" onclick="window.openTradeAnalyzer()">Analyze Trade</button>
                <div id="trade-results"></div>
            </div>
        `;
    }
    renderTradeResults(results) {
        const container = document.getElementById('trade-results');
        if (!container)
            return;
        if (!results || !results.success) {
            container.innerHTML = '<p class="muted-text">Could not analyze trade.</p>';
            return;
        }
        const before = results.before_standings || {};
        const after = results.after_standings || {};
        const impact = results.category_impact || {};
        const cats = Object.keys(impact);
        let impactRows = cats.map(cat => {
            const ci = impact[cat];
            return `<tr>
                <td>${cat}</td>
                <td>${ci.team_a_before?.toFixed(1) ?? '-'}</td>
                <td>${ci.team_a_after?.toFixed(1) ?? '-'}</td>
                <td>${ci.team_b_before?.toFixed(1) ?? '-'}</td>
                <td>${ci.team_b_after?.toFixed(1) ?? '-'}</td>
            </tr>`;
        }).join('');
        container.innerHTML = `
            <div class="trade-results-content">
                <h3>Trade Impact</h3>
                <div class="trade-summary-row">
                    <div class="trade-summary-col">
                        <strong>Team A</strong>
                        <p>Before: Rank ${before.team_a_rank ?? '-'}, ${before.team_a_points?.toFixed(1) ?? '-'} pts</p>
                        <p>After: Rank ${after.team_a_rank ?? '-'}, ${after.team_a_points?.toFixed(1) ?? '-'} pts</p>
                    </div>
                    <div class="trade-summary-col">
                        <strong>Team B</strong>
                        <p>Before: Rank ${before.team_b_rank ?? '-'}, ${before.team_b_points?.toFixed(1) ?? '-'} pts</p>
                        <p>After: Rank ${after.team_b_rank ?? '-'}, ${after.team_b_points?.toFixed(1) ?? '-'} pts</p>
                    </div>
                </div>
                <table class="trade-impact-table">
                    <thead><tr><th>Category</th><th>A Before</th><th>A After</th><th>B Before</th><th>B After</th></tr></thead>
                    <tbody>${impactRows}</tbody>
                </table>
            </div>
        `;
    }
    // ── Feature 9: Win Probability ──────────────────
    renderWinProbability(probability) {
        const container = document.getElementById('win-probability-display');
        if (!container)
            return;
        const pct = Math.round(probability * 100);
        const barWidth = Math.min(pct, 100);
        container.innerHTML = `
            <span class="label">Win Prob:</span>
            <div class="win-prob-bar-container">
                <div class="win-prob-bar" style="width: ${barWidth}%"></div>
            </div>
            <span class="win-prob-pct">${pct}%</span>
        `;
    }
    // ── Feature 10: Draft Recap ─────────────────────
    renderDraftRecap(recap) {
        const container = document.getElementById('recap-content');
        if (!container)
            return;
        if (!recap || !recap.success || !recap.teams || recap.teams.length === 0) {
            container.innerHTML = '<p class="muted-text">No recap available yet…</p>';
            return;
        }
        const teams = recap.teams;
        let rows = teams.map(t => {
            const bestPick = t.best_pick ? `${t.best_pick.player_name} (#${t.best_pick.pick_number})` : '-';
            const reach = t.biggest_reach ? `${t.biggest_reach.player_name} (#${t.biggest_reach.pick_number})` : '-';
            return `<tr>
                <td>${t.team_name}</td>
                <td><span class="grade-badge grade-${t.grade}">${t.grade}</span></td>
                <td>${t.total_points % 1 ? t.total_points.toFixed(1) : t.total_points}</td>
                <td>${t.batting_points % 1 ? t.batting_points.toFixed(1) : t.batting_points}</td>
                <td>${t.pitching_points % 1 ? t.pitching_points.toFixed(1) : t.pitching_points}</td>
                <td>${t.player_count}</td>
                <td>${bestPick}</td>
                <td>${reach}</td>
            </tr>`;
        }).join('');
        container.innerHTML = `
            <div class="recap-container">
                <div class="recap-header">
                    <h3>Draft Recap</h3>
                    <button class="btn-small" onclick="window.exportRecap()">Export to Clipboard</button>
                </div>
                <table class="recap-table">
                    <thead><tr>
                        <th>Team</th><th>Grade</th><th>Total</th><th>Bat</th><th>Pitch</th><th>Players</th><th>Best Pick</th><th>Biggest Reach</th>
                    </tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }
}
//# sourceMappingURL=ui-renderer.js.map