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

/**
 * Standardized tab switching function
 * @param {Event} evt - The click event
 * @param {string} tabName - ID of the tab content to show
 */
function openTab(evt, tabName) {
    let i, tabcontent, tabbuttons;

    // Hide all tab content
    tabcontent = document.getElementsByClassName("tab-content");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }

    // Deactivate all tab buttons (supporting both .tab-button and .tab-btn)
    tabbuttons = document.querySelectorAll(".tab-button, .tab-btn");
    for (i = 0; i < tabbuttons.length; i++) {
        tabbuttons[i].classList.remove("active");
    }

    // Show the specific tab and add an "active" class to the button that opened the tab
    const targetTab = document.getElementById(tabName);
    if (targetTab) {
        targetTab.style.display = "block";
    }

    if (evt && evt.currentTarget) {
        evt.currentTarget.classList.add("active");
    }
}
