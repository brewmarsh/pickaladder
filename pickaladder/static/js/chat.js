/**
 * Real-time Chat Listener for Pickaladder
 */
document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('message-container');
    if (!container) return;

    const cid = container.getAttribute('data-conversation-id');
    const currentUserId = container.getAttribute('data-current-user-id');

    if (!cid || !currentUserId) {
        console.warn('Chat metadata missing from container');
        return;
    }

    // Ensure Firebase is initialized
    if (typeof firebase === 'undefined') {
        console.error('Firebase SDK not loaded');
        return;
    }

    const db = firebase.firestore();
    const messagesRef = db.collection('conversations').doc(cid).collection('messages');

    const renderedMessages = new Set();
    let firstSnapshot = true;

    // Listen for real-time updates
    messagesRef.orderBy('timestamp', 'asc').onSnapshot((snapshot) => {
        if (firstSnapshot) {
            container.innerHTML = '';
            firstSnapshot = false;
        }

        if (snapshot.empty && renderedMessages.size === 0) {
            container.innerHTML = '<div class="flex-grow-1 d-flex align-items-center justify-content-center text-muted"><small>Say hello! 👋</small></div>';
            return;
        }

        snapshot.docChanges().forEach((change) => {
            if (change.type === "added") {
                const msg = change.doc.data();
                const msgId = change.doc.id;
                
                if (!renderedMessages.has(msgId)) {
                    // Remove placeholder if it exists
                    const placeholder = container.querySelector('.text-muted');
                    if (placeholder && (placeholder.textContent.includes('Say hello') || placeholder.textContent.includes('Loading'))) {
                        placeholder.parentElement.remove();
                    }
                    
                    renderMessage(msg, msgId);
                    renderedMessages.add(msgId);
                }
            }
        });
        
        scrollToBottom();
    }, (error) => {
        console.error("Error listening for messages:", error);
        if (error.code === 'permission-denied') {
            container.innerHTML = '<div class="alert alert-danger m-3">You do not have permission to view this chat.</div>';
        }
    });

    /**
     * Renders a single message bubble
     */
    function renderMessage(msg, id) {
        const isMe = msg.senderId === currentUserId;
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble-container d-flex ${isMe ? 'justify-content-end' : ''} mb-3`;
        
        let timeStr = '';
        if (msg.timestamp) {
            const date = msg.timestamp.toDate ? msg.timestamp.toDate() : new Date(msg.timestamp.seconds * 1000);
            timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } else {
            // Local optimistic timestamp if server hasn't set it yet
            timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }

        bubble.innerHTML = `
            <div class="chat-bubble px-3 py-2 rounded shadow-sm ${isMe ? 'bg-volt text-dark' : 'bg-secondary text-white'}" 
                 style="max-width: 75%; overflow-wrap: break-word; position: relative;">
                <div class="message-content" style="font-size: 0.9rem;">${escapeHtml(msg.content)}</div>
                <div class="message-time mt-1 ${isMe ? 'text-dark-50' : 'text-muted'}" style="font-size: 0.65rem; text-align: right;">
                    ${timeStr}
                </div>
            </div>
        `;
        container.appendChild(bubble);
    }

    /**
     * Scrolls the chat container to the bottom
     */
    function scrollToBottom() {
        container.scrollTop = container.scrollHeight;
    }

    /**
     * Simple HTML escape utility
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Intercept form submission for "instant" feel (optional, but requested in task)
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function() {
            // The Firestore listener will pick up the change after the server writes it,
            // or we could optimistically add it here.
            // For now, we rely on Firestore's speed.
            setTimeout(scrollToBottom, 100);
        });
    }
});
