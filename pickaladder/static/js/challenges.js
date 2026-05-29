/**
 * ChallengeUI - Handles all frontend interactions for formal challenges.
 */
const ChallengeUI = {
    modal: null,
    
    init() {
        // Initialize Bootstrap modal if it exists
        const modalEl = document.getElementById('issueChallengeModal');
        if (modalEl) {
            this.modal = new bootstrap.Modal(modalEl);
        }
    },

    /**
     * Open the issue challenge modal.
     */
    openIssueModal(userId, userName, userAvatar) {
        if (userId === currentUserId) {
            showToast("You cannot challenge yourself!", "warning");
            return;
        }

        document.getElementById('challenge-target-id').value = userId;
        document.getElementById('challenge-target-name').textContent = userName;
        document.getElementById('challenge-target-avatar').src = userAvatar || '/static/user_icon.png';
        
        // Update balance display from navbar
        const navBalance = document.querySelector('.credit-balance-nav span');
        if (navBalance) {
            document.getElementById('current-balance-display').textContent = navBalance.textContent;
        }

        this.modal.show();
    },

    /**
     * Submit a new challenge.
     */
    async submitChallenge() {
        const form = document.getElementById('issueChallengeForm');
        const formData = new FormData(form);
        const data = {
            challenged_id: formData.get('challenged_id'),
            wager: parseInt(formData.get('wager'))
        };

        try {
            const response = await fetch('/match/challenge/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            if (result.status === 'success') {
                showToast("Challenge issued successfully!", "success");
                this.modal.hide();
                this.refreshHub();
                // Real-time listener in notifications.js will handle balance update
            } else {
                showToast(result.message || "Failed to issue challenge", "danger");
            }
        } catch (error) {
            console.error('Error issuing challenge:', error);
            showToast("An unexpected error occurred", "danger");
        }
    },

    /**
     * Action handlers for the Challenge Hub.
     */
    async handleAction(challengeId, action) {
        try {
            const response = await fetch(`/match/challenge/${challengeId}/${action}`, {
                method: 'POST'
            });

            const result = await response.json();
            if (result.status === 'success') {
                showToast(`Challenge ${action}ed!`, "success");
                this.refreshHub();
                // Real-time listener in notifications.js handles balance and other UI updates
            } else {
                showToast(result.message || `Failed to ${action} challenge`, "danger");
            }
        } catch (error) {
            console.error(`Error ${action}ing challenge:`, error);
        }
    },

    /**
     * Alias for notifications.js to trigger refresh.
     */
    notifyUpdate() {
        this.refreshHub();
    },

    /**
     * Refresh the Challenge Hub UI on the dashboard.
     */
    async refreshHub() {
        const pendingList = document.getElementById('pending-list');
        const activeList = document.getElementById('active-list');
        const historyList = document.getElementById('history-list');

        if (!pendingList) return; // Not on dashboard

        try {
            const response = await fetch('/match/api/challenges');
            const data = await response.json();

            this.renderList(pendingList, data.pending, 'pending');
            this.renderList(activeList, data.active, 'active');
            this.renderList(historyList, data.history, 'history');
        } catch (error) {
            console.error('Error fetching challenges:', error);
        }
    },

    renderList(container, challenges, type) {
        if (!challenges || challenges.length === 0) {
            container.innerHTML = `<div class="text-center py-3 text-muted">No ${type} challenges.</div>`;
            return;
        }

        container.innerHTML = challenges.map(c => this.renderChallengeCard(c, type)).join('');
    },

    renderChallengeCard(c, type) {
        const isChallenger = c.challenger_id === currentUserId;
        const otherName = isChallenger ? c.challenged_name : c.challenger_name;
        const direction = isChallenger ? "Sent to" : "Received from";
        
        let actions = '';
        let expirationText = '';

        if (type === 'pending') {
            if (isChallenger) {
                actions = `<button class="btn btn-sm btn-outline-danger" onclick="ChallengeUI.handleAction('${c.id}', 'cancel')">Cancel</button>`;
            } else {
                actions = `
                    <button class="btn btn-sm btn-success" onclick="ChallengeUI.handleAction('${c.id}', 'accept')">Accept</button>
                    <button class="btn btn-sm btn-outline-danger" onclick="ChallengeUI.handleAction('${c.id}', 'decline')">Decline</button>
                `;
            }

            // Expiration calculation
            if (c.expires_at) {
                const expires = new Date(c.expires_at);
                const now = new Date();
                const diffMs = expires - now;
                if (diffMs > 0) {
                    const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
                    const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
                    expirationText = `<div class="text-warning fs-xxs mt-1"><i class="far fa-clock"></i> Expires in ${diffHrs}h ${diffMins}m</div>`;
                } else {
                    expirationText = `<div class="text-danger fs-xxs mt-1"><i class="fas fa-exclamation-circle"></i> Expired</div>`;
                }
            }
        }

        return `
            <div class="list-group-item challenge-card ${type} mb-2 shadow-sm border-rounded">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <div class="fw-bold">${direction} ${otherName}</div>
                        <div class="text-muted small">Wager: <span class="wager-badge">🪙 ${c.wager_amount}</span></div>
                        ${expirationText}
                    </div>
                    <div class="challenge-actions">
                        ${actions}
                    </div>
                </div>
            </div>
        `;
    },

    updateNavBalance(delta) {
        const navBalances = document.querySelectorAll('.credit-balance-nav span');
        navBalances.forEach(el => {
            const current = parseInt(el.textContent);
            el.textContent = current + delta;
        });
    }
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => ChallengeUI.init());
