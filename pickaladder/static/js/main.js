document.addEventListener('DOMContentLoaded', function () {
    // Handle form submissions with loading spinner
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function () {
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
        // Auto-dismiss after 4 seconds
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
    });
}
