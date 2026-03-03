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

/**
 * Captures a DOM element as a high-quality canvas, ensuring images are loaded.
 * @param {string} elementId - The ID of the element to capture.
 * @returns {Promise<HTMLCanvasElement>}
 */
/**
 * Shows a loading spinner on a button.
 * @param {HTMLElement} buttonEl - The button element to show the spinner on.
 * @returns {string} The original HTML content of the button.
 */
function showButtonSpinner(buttonEl) {
    if (!buttonEl) return '';
    const originalContent = buttonEl.innerHTML;
    buttonEl.disabled = true;
    buttonEl.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
    return originalContent;
}

/**
 * Hides the loading spinner and restores the button.
 * @param {HTMLElement} buttonEl - The button element.
 * @param {string} originalContent - The original HTML content to restore.
 */
function hideButtonSpinner(buttonEl, originalContent) {
    if (!buttonEl) return;
    buttonEl.disabled = false;
    buttonEl.innerHTML = originalContent;
}

async function captureElement(elementId) {
    const element = document.getElementById(elementId);
    if (!element) throw new Error(`Element with ID ${elementId} not found.`);

    // 1. Wait for all images inside the element to load/decode
    const images = Array.from(element.getElementsByTagName('img'));
    const loadPromises = images.map(img => {
        if (img.complete) {
            return img.decode().catch(() => {}); // Already loaded, just decode
        }
        return new Promise(resolve => {
            img.onload = img.onerror = () => {
                if (img.decode) {
                    img.decode().then(resolve).catch(resolve);
                } else {
                    resolve();
                }
            };
        });
    });

    // Also wait for a small buffer to handle any CSS backgrounds or late renders
    await Promise.all([
        Promise.all(loadPromises),
        new Promise(resolve => setTimeout(resolve, 500))
    ]);

    // 2. Call html2canvas with optimized options
    return html2canvas(element, {
        useCORS: true,            // Handle cross-origin avatars (Firebase/Dicebear)
        allowTaint: false,        // Avoid tainting the canvas
        scale: window.devicePixelRatio || 2, // High-definition rendering
        backgroundColor: null,    // Preserve border-radius (transparent bg)
        logging: false            // Disable logs for cleaner console
    });
}

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
