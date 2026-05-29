/**
 * Handles user feedback submission.
 */
document.addEventListener('DOMContentLoaded', function () {
    const feedbackForm = document.getElementById('feedbackForm');
    const submitBtn = document.getElementById('submitFeedback');
    const loadingSpinner = document.getElementById('feedbackLoading');

    if (submitBtn) {
        submitBtn.addEventListener('click', function () {
            const feedbackType = document.getElementById('feedbackType').value;
            const feedbackMessage = document.getElementById('feedbackMessage').value;

            if (!feedbackMessage) {
                showToast('Please enter a message.', 'warning');
                return;
            }

            // Show loading state
            submitBtn.disabled = true;
            loadingSpinner.classList.remove('d-none');

            fetch('/api/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    type: feedbackType,
                    message: feedbackMessage
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showToast(data.message || 'Feedback submitted successfully!', 'success');
                    // Reset form and close modal
                    feedbackForm.reset();
                    $('#feedbackModal').modal('hide');
                } else {
                    showToast(data.error || 'Failed to submit feedback.', 'danger');
                }
            })
            .catch(error => {
                console.error('Error submitting feedback:', error);
                showToast('An error occurred. Please try again.', 'danger');
            })
            .finally(() => {
                // Hide loading state
                submitBtn.disabled = false;
                loadingSpinner.classList.add('d-none');
            });
        });
    }
});
