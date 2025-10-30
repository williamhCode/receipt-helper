import { fetchGroupVersion } from '$lib/api';

interface PollingState {
    status: 'idle' | 'polling' | 'paused' | 'error';
    error: string | null;
}

export class PollingStore {
    private intervalId: number | null = null;
    private groupId: number | null = null;
    private lastVersion: string | null = null;
    private pollingInterval = 5000; // 5 seconds
    private isDocumentVisible = true;

    // Reactive state using Svelte 5 runes
    public state = $state<PollingState>({
        status: 'idle',
        error: null
    });

    // Callback for when group changes are detected
    public onGroupChanged: (() => void) | null = null;

    constructor() {
        // Set up Page Visibility API to pause polling when tab is inactive
        if (typeof document !== 'undefined') {
            document.addEventListener('visibilitychange', () => {
                this.isDocumentVisible = !document.hidden;

                if (this.isDocumentVisible && this.state.status === 'paused') {
                    console.log('PollingStore: Tab became visible, resuming polling');
                    this.resume();
                } else if (!this.isDocumentVisible && this.state.status === 'polling') {
                    console.log('PollingStore: Tab became hidden, pausing polling');
                    this.pause();
                }
            });
        }
    }

    /**
     * Start polling for updates on a specific group
     */
    start(groupId: number): void {
        // If already polling this group, do nothing
        if (this.intervalId !== null && this.groupId === groupId) {
            console.log(`PollingStore: Already polling group ${groupId}`);
            return;
        }

        // Stop any existing polling
        this.stop();

        this.groupId = groupId;
        this.lastVersion = null;
        this.state.status = 'polling';
        this.state.error = null;

        console.log(`PollingStore: Starting polling for group ${groupId} every ${this.pollingInterval}ms`);

        // Do an initial check immediately
        this.checkForUpdates();

        // Then set up interval for subsequent checks
        this.intervalId = window.setInterval(() => {
            this.checkForUpdates();
        }, this.pollingInterval);
    }

    /**
     * Stop polling
     */
    stop(): void {
        if (this.intervalId !== null) {
            console.log('PollingStore: Stopping polling');
            clearInterval(this.intervalId);
            this.intervalId = null;
        }

        this.groupId = null;
        this.lastVersion = null;
        this.state.status = 'idle';
        this.state.error = null;
    }

    /**
     * Pause polling (when tab is hidden)
     */
    private pause(): void {
        if (this.intervalId !== null) {
            clearInterval(this.intervalId);
            this.intervalId = null;
            this.state.status = 'paused';
        }
    }

    /**
     * Resume polling (when tab becomes visible again)
     */
    private resume(): void {
        if (this.groupId !== null && this.intervalId === null) {
            this.state.status = 'polling';

            // Check immediately on resume
            this.checkForUpdates();

            // Restart interval
            this.intervalId = window.setInterval(() => {
                this.checkForUpdates();
            }, this.pollingInterval);
        }
    }

    /**
     * Check if the group has been updated
     */
    private async checkForUpdates(): Promise<void> {
        if (this.groupId === null) {
            return;
        }

        try {
            const { updated_at } = await fetchGroupVersion(this.groupId);

            // If this is the first check, just store the version
            if (this.lastVersion === null) {
                this.lastVersion = updated_at;
                return;
            }

            // If version changed, trigger refresh
            if (updated_at !== this.lastVersion) {
                this.lastVersion = updated_at;

                if (this.onGroupChanged) {
                    this.onGroupChanged();
                }
            }

            // Clear any previous errors
            if (this.state.error) {
                this.state.error = null;
            }
        } catch (error) {
            console.error('PollingStore: Error checking for updates:', error);
            this.state.status = 'error';
            this.state.error = error instanceof Error ? error.message : 'Unknown error';
        }
    }

    /**
     * Update the last known version after making local changes
     * This prevents the next poll from triggering an unnecessary refresh
     */
    updateVersion(version: string): void {
        this.lastVersion = version;
    }

    // Computed getters
    get isPolling(): boolean {
        return this.state.status === 'polling';
    }

    get isPaused(): boolean {
        return this.state.status === 'paused';
    }

    get hasError(): boolean {
        return this.state.status === 'error';
    }

    get statusText(): string {
        switch (this.state.status) {
            case 'polling': return 'Live';
            case 'paused': return 'Paused';
            case 'idle': return 'Offline';
            case 'error': return 'Error';
            default: return 'Unknown';
        }
    }

    get currentGroupId(): number | null {
        return this.groupId;
    }
}

export const pollingStore = new PollingStore();
