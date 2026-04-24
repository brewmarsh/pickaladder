/**
 * IndexedDB storage for offline match submissions.
 */

const DB_NAME = 'pickaladder_offline';
const DB_VERSION = 1;
const STORE_NAME = 'pending_matches';

class OfflineStore {
    constructor() {
        this.db = null;
    }

    async init() {
        if (this.db) return;

        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);

            request.onerror = (event) => {
                console.error('IndexedDB error:', event.target.error);
                reject(event.target.error);
            };

            request.onsuccess = (event) => {
                this.db = event.target.result;
                resolve();
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
                }
            };
        });
    }

    async saveMatch(matchData) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            
            const payload = {
                ...matchData,
                offlineAt: new Date().toISOString()
            };

            const request = store.add(payload);

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async getPendingMatches() {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_NAME], 'readonly');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.getAll();

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async removeMatch(id) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.delete(id);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    async clear() {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.clear();

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    async triggerSync() {
        const pending = await this.getPendingMatches();
        if (pending.length === 0) return;

        console.log(`Syncing ${pending.length} matches...`);
        const statusToast = document.getElementById('sync-status');
        const countSpan = document.getElementById('pending-sync-count');
        
        if (statusToast) {
            countSpan.textContent = pending.length;
            statusToast.style.display = 'block';
        }

        for (const match of pending) {
            try {
                const response = await fetch('/match/record', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                    },
                    body: JSON.stringify(match)
                });

                if (response.ok) {
                    await this.removeMatch(match.id);
                } else {
                    console.error('Failed to sync match:', await response.text());
                }
            } catch (err) {
                console.error('Network error during sync:', err);
                break; // Stop syncing if network fails again
            }
        }

        if (statusToast) {
            statusToast.style.display = 'none';
        }
    }
}

const offlineStore = new OfflineStore();
window.offlineStore = offlineStore;

window.triggerOfflineSync = function() {
    offlineStore.triggerSync();
};
