// Intercept fetch to add CSRF and Auth tokens
(function () {
    const originalFetch = window.fetch;
    window.fetch = function (url, options) {
        options = options || {};
        options.headers = options.headers || {};

        // Add CSRF token for non-safe methods
        const method = (options.method || 'GET').toUpperCase();
        const safeMethods = ['GET', 'HEAD', 'OPTIONS', 'TRACE'];
        if (!safeMethods.includes(method)) {
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            if (csrfMeta) {
                options.headers['X-CSRFToken'] = csrfMeta.getAttribute('content');
            }
        }

        // Add Firebase Auth token if available
        const token = localStorage.getItem('firebaseIdToken');
        if (token) {
            options.headers['Authorization'] = 'Bearer ' + token;
        }

        return originalFetch(url, options);
    };
})();

document.addEventListener('DOMContentLoaded', function () {
    // Handle form submissions with loading spinner
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function () {
            // Disable spinner in E2E tests to avoid flakiness
            if (document.body.dataset.isTesting === 'true') return;

            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                // Store original text
                submitBtn.dataset.originalText = submitBtn.innerHTML;

                // Disable the button
                submitBtn.disabled = true;

                // Replace text with spinner
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
            }
        });
    });

    // Handle flash messages
    handleFlashMessages();
});

function handleFlashMessages() {
    const toasts = document.querySelectorAll('.toast');

    toasts.forEach(toast => {
        // Auto-dismiss after 4 seconds unless data-autohide="false" or in testing
        const isTesting = document.body.dataset.isTesting === 'true';
        const autohide = toast.dataset.autohide !== 'false' && !isTesting;

        if (autohide) {
            const dismissTimeout = setTimeout(() => {
                if (toast.parentNode) {
                    toast.classList.add('fade-out');
                    setTimeout(() => {
                        if (toast.parentNode) {
                            toast.remove();
                        }
                    }, 500); // Wait for the 0.5s transition
                }
            }, 4000);

            // Click to dismiss
            const closeButton = toast.querySelector('.close');
            if (closeButton) {
                closeButton.addEventListener('click', function (e) {
                    e.preventDefault();
                    clearTimeout(dismissTimeout);
                    toast.remove();
                });
            }
        } else {
            // Even if not autohiding, still allow manual dismissal
            const closeButton = toast.querySelector('.close');
            if (closeButton) {
                closeButton.addEventListener('click', function (e) {
                    e.preventDefault();
                    toast.remove();
                });
            }
        }
    });
}
