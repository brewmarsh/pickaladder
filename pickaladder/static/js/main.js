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

    // Global click handler for clickable rows
    document.addEventListener("click", (e) => {
        const row = e.target.closest(".clickable-row");
        if (row && row.dataset.href && !e.target.closest("a") && !e.target.closest("button") && !e.target.closest("input")) {
            window.location.href = row.dataset.href;
        }
    });
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

/**
 * Handles the "Share" button click: shows a loading state, captures the element,
 * and copies the resulting image to the clipboard.
 * @param {string} buttonId - The ID of the button that was clicked.
 * @param {string} targetElementId - The ID of the element to capture as an image.
 */
async function handleShareClick(buttonId, targetElementId) {
    const buttonEl = document.getElementById(buttonId);
    if (!buttonEl) return;

    const originalHTML = buttonEl.innerHTML;
    buttonEl.disabled = true;
    buttonEl.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...';

    try {
        const canvas = await captureElement(targetElementId);
        await copyCanvasToClipboard(canvas, buttonEl, originalHTML);
    } catch (err) {
        console.error('Share failed:', err);
        buttonEl.innerHTML = originalHTML;
    } finally {
        buttonEl.disabled = false;
    }
}

/**
 * Copies a canvas image to the clipboard.
 * Optimized for Safari's asynchronous clipboard security model.
 * @param {HTMLCanvasElement} canvas - The canvas to copy.
 * @param {HTMLElement} buttonEl - Optional button element to show success state on.
 * @param {string} originalHTML - Optional original HTML to restore after success.
 * @returns {Promise<void>}
 */
function copyCanvasToClipboard(canvas, buttonEl, originalHTML) {
    try {
        // Safari Fix: Instead of awaiting the blob, we pass a function that returns
        // a Promise for the blob directly into the ClipboardItem dictionary.
        // This keeps the navigator.clipboard.write call synchronous within the user gesture.
        const clipboardItem = new ClipboardItem({
            "image/png": () => new Promise((resolve, reject) => {
                if (!canvas.toBlob) {
                    reject(new Error("Canvas.toBlob not supported"));
                    return;
                }
                canvas.toBlob(blob => {
                    if (blob) resolve(blob);
                    else reject(new Error("Canvas toBlob failed"));
                }, 'image/png');
            })
        });

        return navigator.clipboard.write([clipboardItem]).then(() => {
            if (typeof showToast === 'function') {
                showToast("Image copied to clipboard!", "success");
            }

            if (buttonEl) {
                const contentToRestore = originalHTML || buttonEl.innerHTML;
                buttonEl.innerHTML = '<i class="fas fa-check"></i> Copied!';
                setTimeout(() => {
                    buttonEl.innerHTML = contentToRestore;
                }, 2000);
            }
        }).catch(err => {
            console.error('Clipboard write failed, falling back to download:', err);
            return fallbackToDownload(canvas, buttonEl, originalHTML);
        });
    } catch (err) {
        console.error('Clipboard API failed, falling back to download:', err);
        return fallbackToDownload(canvas, buttonEl, originalHTML);
    }
}

/**
 * Fallback to downloading the image if clipboard write fails.
 * @param {HTMLCanvasElement} canvas - The canvas to download.
 * @param {HTMLElement} buttonEl - Optional button element to restore.
 * @param {string} originalHTML - Optional original HTML to restore.
 */
function fallbackToDownload(canvas, buttonEl, originalHTML) {
    downloadCanvas(canvas, 'match-result.png');
    if (typeof showToast === 'function') {
        showToast("Saved image to your device!", "success");
    }
    if (buttonEl && originalHTML) {
        buttonEl.innerHTML = originalHTML;
    }
}

function downloadCanvas(canvas, filename) {
    const link = document.createElement('a');
    link.download = filename || 'share-card.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
}

function dismissToast(toast) {
    if (!toast || !toast.parentNode) return;
    toast.classList.add('fade-out');
    setTimeout(() => {
        if (toast.parentNode) {
            toast.remove();
        }
    }, 500);
}

function showToast(message, category = 'info', submissionId = null) {
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) return;

    const toastId = submissionId || `toast_${Date.now()}`;
    const isTesting = document.body.dataset.isTesting === 'true';
    const autohide = category !== 'info' && !isTesting; // Don't autohide pending toasts or in tests
    const delay = 4000;
    const logoUrl = document.body.dataset.logoUrl || '/static/pickaladder_logo_64.png';

    let progressBar = '';
    if (category === 'info') {
        progressBar = '<div class="progress"><div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: 100%"></div></div>';
    }

    const toastHTML = `
        <div class="toast show alert-${category}" id="${toastId}" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header">
                <img src="${logoUrl}" class="rounded mr-2" alt="Logo" style="width: 20px; height: 20px;">
                <strong>pickaladder</strong>
                <button type="button" class="close" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
            <div class="toast-body">
                ${message}
                ${progressBar}
            </div>
        </div>
    `;
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);
    const newToast = document.getElementById(toastId);

    // Handle close button
    const closeBtn = newToast.querySelector('.close');
    closeBtn.onclick = () => dismissToast(newToast);

    // Auto-dismiss
    if (autohide) {
        setTimeout(() => dismissToast(newToast), delay);
    }

    return toastId;
}

function updateToast(toastId, message, category) {
    const toastElement = document.getElementById(toastId);
    if (!toastElement) return;

    const toastBody = toastElement.querySelector('.toast-body');

    // Remove progress bar
    const progressBar = toastBody.querySelector('.progress');
    if (progressBar) {
        progressBar.remove();
    }

    toastBody.innerHTML = message;

    // Add a retry button for failed submissions
    if (category === 'danger') {
        const retryButton = document.createElement('button');
        retryButton.className = 'btn btn-sm btn-link';
        retryButton.innerText = 'Retry';
        retryButton.onclick = function () {
            if (window.optimisticSubmission) {
                window.optimisticSubmission.retrySubmission(toastId);
            }
        };
        toastBody.appendChild(document.createElement('br'));
        toastBody.appendChild(retryButton);
    }

    // Start auto-dismiss now that it's no longer "pending"
    if (category !== 'info') {
        setTimeout(() => dismissToast(toastElement), 4000);
    }
}
