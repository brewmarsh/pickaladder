/**
 * auth.js - Shared Authentication & Registration Logic
 */

const AuthModule = {
    /**
     * Check if a username is available.
     * @param {string} username
     * @returns {Promise<boolean>}
     */
    async checkUsernameAvailability(username) {
        if (!username || username.length < 3) return false;
        try {
            const response = await fetch(`/auth/check_username?username=${encodeURIComponent(username)}`);
            const data = await response.json();
            return data.available;
        } catch (error) {
            console.error("Error checking username:", error);
            return false;
        }
    },

    /**
     * Handle common Firebase Auth error codes.
     * @param {Error} error
     * @returns {string} User-friendly error message
     */
    getErrorMessage(error) {
        switch (error.code) {
            case 'auth/email-already-in-use':
                return 'This email is already registered. Try logging in instead.';
            case 'auth/invalid-email':
                return 'Please enter a valid email address.';
            case 'auth/weak-password':
                return 'Password is too weak. Please use at least 8 characters.';
            case 'auth/user-not-found':
            case 'auth/wrong-password':
            case 'auth/invalid-login-credentials':
                return 'Invalid email or password.';
            case 'auth/network-request-failed':
                return 'Network error. Please check your connection.';
            default:
                return error.message || 'An unexpected error occurred. Please try again.';
        }
    },

    /**
     * Redirect after successful login/registration.
     */
    handleAuthSuccess() {
        const urlParams = new URLSearchParams(window.location.search);
        const nextUrl = urlParams.get('next');
        if (nextUrl && nextUrl.startsWith('/')) {
            window.location.href = nextUrl;
        } else {
            window.location.href = "/user/dashboard";
        }
    },

    /**
     * Shared Google Sign-in logic.
     * @param {boolean} remember
     */
    async handleGoogleSignIn(remember = false) {
        const provider = new firebase.auth.GoogleAuthProvider();
        try {
            const result = await firebase.auth().signInWithPopup(provider);
            const idToken = await result.user.getIdToken();
            localStorage.setItem('firebaseIdToken', idToken);

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

            const response = await fetch("/auth/session_login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify({ idToken: idToken, remember: remember }),
            });

            if (response.ok) {
                this.handleAuthSuccess();
            } else {
                throw new Error("Server-side session creation failed.");
            }
        } catch (error) {
            console.error("Google Sign-in error:", error);
            throw error;
        }
    },

    /**
     * Registration logic (Email/Password).
     * @param {Object} registrationData
     */
    async handleRegistration(registrationData) {
        const { email, password, username, name, duprRating } = registrationData;
        try {
            const userCredential = await firebase.auth().createUserWithEmailAndPassword(email, password);
            const idToken = await userCredential.user.getIdToken();
            localStorage.setItem('firebaseIdToken', idToken);

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

            const response = await fetch("/auth/session_login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify({
                    idToken: idToken,
                    registrationData: {
                        username,
                        name,
                        duprRating
                    }
                }),
            });

            if (response.ok) {
                this.handleAuthSuccess();
            } else {
                throw new Error("Profile creation failed on server.");
            }
        } catch (error) {
            console.error("Registration error:", error);
            throw error;
        }
    }
};

window.AuthModule = AuthModule;
