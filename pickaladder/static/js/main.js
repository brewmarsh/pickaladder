document.addEventListener('DOMContentLoaded', function () {
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
});
