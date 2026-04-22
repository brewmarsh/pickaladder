document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('team-wizard-form');
    const steps = document.querySelectorAll('.wizard-step');
    const dots = document.querySelectorAll('.step-dot');
    const nextBtns = document.querySelectorAll('.next-step');
    const prevBtns = document.querySelectorAll('.prev-step');
    let currentStep = 0;

    const teamData = {
        name: '',
        description: '',
        member_ids: []
    };

    function showStep(n) {
        steps.forEach((step, index) => {
            step.classList.toggle('active', index === n);
        });
        dots.forEach((dot, index) => {
            dot.classList.toggle('active', index === n);
        });
        
        if (n === 2) {
            updateConfirmation();
        }
    }

    function updateConfirmation() {
        teamData.name = document.getElementById('team-name').value;
        teamData.description = document.getElementById('team-description').value;
        
        document.getElementById('confirm-name').textContent = teamData.name;
        document.getElementById('confirm-description').textContent = teamData.description || 'None';
        
        const rosterList = document.getElementById('confirm-roster');
        rosterList.innerHTML = '<li>You (Captain)</li>';
        
        const selectedMembers = document.querySelectorAll('.member-item.selected');
        teamData.member_ids = [];
        selectedMembers.forEach(item => {
            const id = item.getAttribute('data-id');
            const name = item.getAttribute('data-name');
            teamData.member_ids.push(id);
            const li = document.createElement('li');
            li.textContent = name;
            rosterList.appendChild(li);
        });
    }

    nextBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            if (validateStep(currentStep)) {
                currentStep++;
                showStep(currentStep);
            }
        });
    });

    prevBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            currentStep--;
            showStep(currentStep);
        });
    });

    function validateStep(n) {
        if (n === 0) {
            const name = document.getElementById('team-name').value;
            if (!name.trim()) {
                alert('Please enter a team name.');
                return false;
            }
        }
        return true;
    }

    // Member Selection Logic
    const memberItems = document.querySelectorAll('.member-item');
    memberItems.forEach(item => {
        item.addEventListener('click', function(e) {
            // Don't toggle if clicking the checkbox directly (it will toggle itself)
            if (e.target.classList.contains('member-checkbox')) return;
            
            this.classList.toggle('selected');
            const checkbox = this.querySelector('.member-checkbox');
            checkbox.checked = !checkbox.checked;
        });
    });

    // Search Logic
    const searchInput = document.getElementById('member-search');
    searchInput.addEventListener('input', function() {
        const query = this.value.toLowerCase();
        memberItems.forEach(item => {
            const name = item.getAttribute('data-name').toLowerCase();
            item.style.display = name.includes(query) ? 'flex' : 'none';
        });
    });

    // Form Submission
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Creating...';
        
        const errorDiv = document.getElementById('wizard-error');
        errorDiv.classList.add('d-none');

        fetch(window.location.pathname, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': document.querySelector('input[name="csrf_token"]').value
            },
            body: JSON.stringify(teamData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = data.redirect;
            } else {
                errorDiv.textContent = data.error || 'An unexpected error occurred.';
                errorDiv.classList.remove('d-none');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Create Team';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            errorDiv.textContent = 'A network error occurred. Please try again.';
            errorDiv.classList.remove('d-none');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Create Team';
        });
    });
});
