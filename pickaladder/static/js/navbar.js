document.addEventListener('DOMContentLoaded', function () {
    const hamburger = document.querySelector('.hamburger-menu');
    const mobileNav = document.getElementById('myLinks');

    if (hamburger && mobileNav) {
        hamburger.addEventListener('click', function () {
            // Toggle Menu: Toggle the d-none class on #myLinks
            mobileNav.classList.toggle('d-none');

            // Animate Icon: Toggle active class on the hamburger button
            hamburger.classList.toggle('active');
        });
    }
});
