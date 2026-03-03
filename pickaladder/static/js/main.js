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
 * Copies a canvas image to the clipboard.
 * Optimized for Safari's asynchronous clipboard security model.
 */
function copyCanvasToClipboard(canvas, buttonEl) {
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

        navigator.clipboard.write([clipboardItem]).then(() => {
            if (typeof showToast === 'function') {
                showToast("Image copied to clipboard!", "success");
            }

            if (buttonEl) {
                const originalContent = buttonEl.innerHTML;
                buttonEl.innerHTML = '<i class="fas fa-check"></i> Copied!';
                setTimeout(() => {
                    buttonEl.innerHTML = originalContent;
                }, 2000);
            }
        }).catch(err => {
            console.error('Clipboard write failed, falling back to download:', err);
            fallbackToDownload(canvas, buttonEl);
        });
    } catch (err) {
        console.error('Clipboard API failed, falling back to download:', err);
        fallbackToDownload(canvas, buttonEl);
    }
}

/**
 * Fallback to downloading the image if clipboard write fails.
 */
function fallbackToDownload(canvas, buttonEl) {
    downloadCanvas(canvas, 'match-result.png');
    if (typeof showToast === 'function') {
        showToast("Saved image to your device!", "success");
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
