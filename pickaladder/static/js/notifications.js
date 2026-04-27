/**
 * Real-time Notifications & Push Integration
 */

(function () {
    if (!currentUserId) return;

    const db = firebase.firestore();
    const messaging = firebase.messaging();
    let isInitialLoad = true;
    let previousUnreadCounts = {};

    // 1. Listen for real-time conversation updates
    db.collection("conversations")
        .where("participants", "array_contains", currentUserId)
        .onSnapshot((snapshot) => {
            let totalUnread = 0;
            let newMessagesFound = [];

            snapshot.forEach((doc) => {
                const data = doc.to_dict();
                const unreadCount = (data.unreadCount && data.unreadCount[currentUserId]) || 0;
                totalUnread += unreadCount;

                // Detect if this conversation has a NEW unread message
                const prevCount = previousUnreadCounts[doc.id] || 0;
                if (!isInitialLoad && unreadCount > prevCount) {
                    // Only notify if we are NOT currently viewing this specific conversation
                    const isViewingConversation = window.location.pathname.includes(`/messaging/conversation/${doc.id}`);
                    if (!isViewingConversation) {
                        newMessagesFound.push({
                            id: doc.id,
                            content: data.lastMessage,
                            senderId: data.lastMessageSenderId
                        });
                    }
                }
                previousUnreadCounts[doc.id] = unreadCount;
            });

            updateUnreadBadges(totalUnread);

            if (!isInitialLoad && newMessagesFound.length > 0) {
                newMessagesFound.forEach(msg => {
                    // We don't have the sender's name here easily without another query, 
                    // but we can show the message content or a generic notification.
                    showToast(`New message: "${msg.content}"`, 'info');
                });
            }

            isInitialLoad = false;
        }, (error) => {
            console.error("Firestore listener error:", error);
        });

    /**
     * Updates the unread message badges in the navbar
     */
    function updateUnreadBadges(count) {
        const badges = [
            document.getElementById('unread-messages-badge'),
            document.getElementById('unread-messages-badge-mobile')
        ];

        badges.forEach(badge => {
            if (!badge) return;
            if (count > 0) {
                badge.innerText = count;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        });
    }

    // 2. Listen for Challenge Updates
    let previousChallengeStatuses = {};
    let isInitialChallengesLoad = true;

    function handleChallengeUpdate(doc) {
        const data = doc.data();
        const id = doc.id;
        const status = data.status;
        const prevStatus = previousChallengeStatuses[id];

        if (!isInitialChallengesLoad && status !== prevStatus) {
            if (status === 'pending' && data.challenged_id === currentUserId) {
                showToast(`New Challenge from ${data.challenger_name || 'a player'}!`, 'info');
            } else if (status === 'accepted') {
                if (data.challenger_id === currentUserId) {
                    showToast(`Challenge accepted by ${data.challenged_name || 'player'}!`, 'success');
                }
            } else if (status === 'declined') {
                if (data.challenger_id === currentUserId) {
                    showToast(`Challenge declined by ${data.challenged_name || 'player'}.`, 'warning');
                }
            } else if (status === 'completed') {
                showToast(`Challenge resolved!`, 'success');
            } else if (status === 'expired') {
                showToast(`Challenge expired.`, 'secondary');
            }
            
            // Trigger UI refresh if ChallengeUI is available
            if (window.ChallengeUI && typeof window.ChallengeUI.refreshHub === 'function') {
                window.ChallengeUI.refreshHub();
            }
        }
        previousChallengeStatuses[id] = status;
    }

    db.collection("challenges")
        .where("challenger_id", "==", currentUserId)
        .onSnapshot(snapshot => {
            snapshot.docChanges().forEach(change => {
                handleChallengeUpdate(change.doc);
            });
            isInitialChallengesLoad = false;
        }, (error) => console.error("Challenge listener error (challenger):", error));

    db.collection("challenges")
        .where("challenged_id", "==", currentUserId)
        .onSnapshot(snapshot => {
            snapshot.docChanges().forEach(change => {
                handleChallengeUpdate(change.doc);
            });
            isInitialChallengesLoad = false;
        }, (error) => console.error("Challenge listener error (challenged):", error));

    // 3. Listen for User Credit Balance
    db.collection("users").doc(currentUserId)
        .onSnapshot(doc => {
            if (doc.exists) {
                const data = doc.data();
                const credits = data.social_credits !== undefined ? data.social_credits : 100;
                document.querySelectorAll('.credit-balance-nav span').forEach(el => {
                    el.innerText = credits;
                });
            }
        }, (error) => console.error("User credit listener error:", error));

    // 4. FCM Push Notification Setup
    setupPushNotifications();

    function setupPushNotifications() {
        // Request permission and get token
        messaging.getToken({ vapidKey: 'BMY8eE-lP_8R4Z-4J6X-3f1_m5v8G8K5kG9P_f4z5E7X9v8w7P5L8z9k5M8P7z6w5C4v3u2t1s0r' }) // Using a placeholder VAPID key - in production this should be configured via env
            .then((currentToken) => {
                if (currentToken) {
                    saveTokenToServer(currentToken);
                } else {
                    console.log('No registration token available. Request permission to generate one.');
                }
            }).catch((err) => {
                console.log('An error occurred while retrieving token. ', err);
            });

        // Handle incoming messages while the app is in the foreground
        messaging.onMessage((payload) => {
            console.log('Message received. ', payload);
            const { title, body } = payload.notification;
            showToast(`${title}: ${body}`, 'info');
        });
    }

    function saveTokenToServer(token) {
        const lastToken = localStorage.getItem('fcmToken');
        if (lastToken === token) return; // Already saved

        fetch('/api/save_fcm_token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ token: token }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                localStorage.setItem('fcmToken', token);
            }
        })
        .catch((error) => {
            console.error('Error saving FCM token:', error);
        });
    }

})();
