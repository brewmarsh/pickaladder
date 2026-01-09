// optimistic_submission.js

(function() {
    const PENDING_MATCHES_KEY = 'pendingMatches';

    function getPendingMatches() {
        return JSON.parse(localStorage.getItem(PENDING_MATCHES_KEY)) || [];
    }

    function savePendingMatches(matches) {
        localStorage.setItem(PENDING_MATCHES_KEY, JSON.stringify(matches));
    }

    window.optimisticSubmission = {
        addPendingMatch: function(matchData) {
            const matches = getPendingMatches();
            matches.push(matchData);
            savePendingMatches(matches);
        },
        getPendingMatches: getPendingMatches,
        clearPendingMatches: function() {
            localStorage.removeItem(PENDING_MATCHES_KEY);
        }
    };
})();
