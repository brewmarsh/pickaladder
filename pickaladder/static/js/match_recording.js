/**
 * JS for Match Recording with Dynamic Teams support.
 */

document.addEventListener('DOMContentLoaded', function() {
    const matchTypeSelect = document.getElementById('match_type');
    const matchDateInput = document.getElementById('match_date');
    if (matchDateInput && !matchDateInput.value) {
        matchDateInput.valueAsDate = new Date();
    }

    // Elements
    const elements = {
        matchType: matchTypeSelect,
        side1ModeManual: document.getElementById('side1_manual'),
        side1ModeTeam: document.getElementById('side1_team'),
        side2ModeManual: document.getElementById('side2_manual'),
        side2ModeTeam: document.getElementById('side2_team'),
        
        side1ManualContainer: document.getElementById('side1-manual-container'),
        side1TeamContainer: document.getElementById('side1-team-container'),
        side2ManualContainer: document.getElementById('side2-manual-container'),
        side2TeamContainer: document.getElementById('side2-team-container'),

        side1TeamSelect: document.getElementById('side1_team_select'),
        side2TeamSelect: document.getElementById('side2_team_select'),

        side1RosterContainer: document.getElementById('side1-roster-container'),
        side2RosterContainer: document.getElementById('side2-roster-container'),
        side1RosterList: document.getElementById('side1-roster-list'),
        side2RosterList: document.getElementById('side2-roster-list'),

        partnerGroup: document.getElementById('partner-group'),
        opponent2Group: document.getElementById('opponent2-group'),
        
        player1: document.getElementById('player1'),
        partner: document.getElementById('partner'),
        player2: document.getElementById('player2'),
        opponent2: document.getElementById('opponent2'),

        namedTeam1Id: document.getElementById('named_team_1_id'),
        namedTeam2Id: document.getElementById('named_team_2_id'),

        player1ScoreLabel: document.getElementById('player1-score-label'),
        player2Label: document.getElementById('player2-label'),
        player2ScoreLabel: document.getElementById('player2-score-label'),

        predictionPreview: document.getElementById('prediction-preview')
    };

    const playerDropdowns = [elements.player1, elements.partner, elements.player2, elements.opponent2];

    // Initialize
    fetchUserTeams();
    toggleFields();
    updateDropdowns();

    // Event Listeners
    if (elements.matchType) {
        elements.matchType.addEventListener('change', toggleFields);
    }

    document.querySelectorAll('input[name="side1_mode"]').forEach(input => {
        input.addEventListener('change', () => toggleSideMode(1));
    });

    document.querySelectorAll('input[name="side2_mode"]').forEach(input => {
        input.addEventListener('change', () => toggleSideMode(2));
    });

    if (elements.side1TeamSelect) {
        elements.side1TeamSelect.addEventListener('change', () => loadRoster(1));
    }

    if (elements.side2TeamSelect) {
        elements.side2TeamSelect.addEventListener('change', () => loadRoster(2));
    }

    playerDropdowns.forEach(dropdown => {
        if (dropdown) {
            dropdown.addEventListener('change', updateDropdowns);
        }
    });

    function toggleFields() {
        const matchType = elements.matchType.value;
        const isDoubles = (matchType === 'doubles');

        elements.partnerGroup.style.display = isDoubles ? 'block' : 'none';
        elements.opponent2Group.style.display = isDoubles ? 'block' : 'none';

        if (isDoubles) {
            elements.player1ScoreLabel.innerText = 'Team 1 Score';
            elements.player2Label.innerText = 'Opponent 1';
            elements.player2ScoreLabel.innerText = 'Team 2 Score';
        } else {
            elements.player1ScoreLabel.innerText = 'Your Score';
            elements.player2Label.innerText = 'Opponent';
            elements.player2ScoreLabel.innerText = "Opponent's Score";
        }
        
        checkPredictionVisibility();
        // Re-render rosters if modes are 'team' because requirements changed (1 vs 2 players)
        if (elements.side1ModeTeam.checked) loadRoster(1);
        if (elements.side2ModeTeam.checked) loadRoster(2);
    }

    function toggleSideMode(side) {
        const isTeamMode = document.getElementById(`side${side}_team`).checked;
        const manualContainer = document.getElementById(`side${side}-manual-container`);
        const teamContainer = document.getElementById(`side${side}-team-container`);

        if (isTeamMode) {
            manualContainer.style.display = 'none';
            teamContainer.style.display = 'block';
            // Clear manual selections for this side
            if (side === 1) {
                elements.player1.value = "";
                elements.partner.value = "";
                elements.namedTeam1Id.value = elements.side1TeamSelect.value;
            } else {
                elements.player2.value = "";
                elements.opponent2.value = "";
                elements.namedTeam2Id.value = elements.side2TeamSelect.value;
            }
        } else {
            manualContainer.style.display = 'block';
            teamContainer.style.display = 'none';
            if (side === 1) {
                elements.namedTeam1Id.value = "";
            } else {
                elements.namedTeam2Id.value = "";
            }
        }
        updateDropdowns();
    }

    function fetchUserTeams() {
        fetch('/team/api/user-teams')
            .then(response => response.json())
            .then(data => {
                const teams = data.teams;
                [elements.side1TeamSelect, elements.side2TeamSelect].forEach(select => {
                    if (select) {
                        teams.forEach(team => {
                            const option = document.createElement('option');
                            option.value = team.id;
                            option.textContent = team.name;
                            select.appendChild(option);
                        });
                    }
                });
            })
            .catch(error => console.error('Error fetching teams:', error));
    }

    function loadRoster(side) {
        const teamId = document.getElementById(`side${side}_team_select`).value;
        const rosterContainer = document.getElementById(`side${side}-roster-container`);
        const rosterList = document.getElementById(`side${side}-roster-list`);
        const namedTeamIdInput = document.getElementById(`named_team_${side}_id`);

        namedTeamIdInput.value = teamId;

        if (!teamId) {
            rosterContainer.style.display = 'none';
            return;
        }

        fetch(`/team/api/${teamId}/roster`)
            .then(response => response.json())
            .then(data => {
                rosterList.innerHTML = '';
                data.members.forEach(member => {
                    const div = document.createElement('div');
                    div.className = 'form-check';
                    div.innerHTML = `
                        <input class="form-check-input roster-check-${side}" type="checkbox" value="${member.id}" id="side${side}_member_${member.id}" onchange="handleRosterSelection(${side})">
                        <label class="form-check-label" for="side${side}_member_${member.id}">
                            ${member.name}
                        </label>
                    `;
                    rosterList.appendChild(div);
                });
                rosterContainer.style.display = 'block';
                // Reset selections
                if (side === 1) {
                    elements.player1.value = "";
                    elements.partner.value = "";
                } else {
                    elements.player2.value = "";
                    elements.opponent2.value = "";
                }
                updateDropdowns();
            })
            .catch(error => console.error('Error fetching roster:', error));
    }

    window.handleRosterSelection = function(side) {
        const checks = document.querySelectorAll(`.roster-check-${side}:checked`);
        const matchType = elements.matchType.value;
        const requiredCount = (matchType === 'doubles') ? 2 : 1;

        if (checks.length > requiredCount) {
            // Uncheck the last one
            event.target.checked = false;
            alert(`You can only select ${requiredCount} participant(s) for ${matchType} matches.`);
            return;
        }

        // Update hidden/manual dropdowns so form submission works
        const selectedIds = Array.from(checks).map(c => c.value);
        if (side === 1) {
            elements.player1.value = selectedIds[0] || "";
            elements.partner.value = selectedIds[1] || "";
        } else {
            elements.player2.value = selectedIds[0] || "";
            elements.opponent2.value = selectedIds[1] || "";
        }
        updateDropdowns();
    };

    function updateDropdowns() {
        const selectedValues = playerDropdowns.map(dropdown => dropdown.value).filter(Boolean);

        playerDropdowns.forEach(dropdown => {
            if (!dropdown) return;
            Array.from(dropdown.options).forEach(option => {
                if (selectedValues.includes(option.value) && option.value !== dropdown.value) {
                    option.disabled = true;
                } else {
                    option.disabled = false;
                }
            });
        });
        checkPredictionVisibility();
    }

    function checkPredictionVisibility() {
        const p1 = elements.player1.value;
        const p2 = elements.player2.value;
        if (p1 && p2) {
            elements.predictionPreview.style.display = 'block';
        } else {
            elements.predictionPreview.style.display = 'none';
        }
    }

    // Offline Interceptor
    const form = document.getElementById('record-match-form');
    if (form) {
        form.addEventListener('submit', async function(e) {
            if (navigator.onLine) return; // Proceed normally if online

            e.preventDefault();
            console.log('Offline detected. Saving match locally...');

            const formData = new FormData(form);
            const data = {};
            formData.forEach((value, key) => data[key] = value);

            try {
                await window.offlineStore.saveMatch(data);
                
                // Show a fake success message or redirect
                alert('Offline: Match saved locally. It will be uploaded automatically when you reconnect.');
                
                // Redirect back to dashboard to maintain flow
                window.location.href = '/user/dashboard';
            } catch (err) {
                console.error('Failed to save match offline:', err);
                alert('Error saving match offline. Please try again.');
            }
        });
    }
});
