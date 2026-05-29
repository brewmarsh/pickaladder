document.addEventListener('DOMContentLoaded', function () {
    const hamburger = document.querySelector('.hamburger-menu');
    const mobileNav = document.getElementById('myLinks');

    if (hamburger && mobileNav) {
        hamburger.addEventListener('click', function () {
            // Toggle Menu
            mobileNav.classList.toggle('show');

            // Animate Icon: Toggle active class on the hamburger button
            hamburger.classList.toggle('active');
        });
    }
});
