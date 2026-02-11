document.addEventListener('DOMContentLoaded', function () {
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
