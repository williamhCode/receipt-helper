// src/lib/stores/realtime.svelte.ts

import { RealtimeReceiptManager } from '$lib/websocket.js';
import { updateReceiptEntry } from '$lib/utils.js';

interface ConnectionState {
    status: 'disconnected' | 'connecting' | 'connected' | 'error';
    error: string | null;
}

export class RealtimeStore {
    private manager: RealtimeReceiptManager | null = null;
    private groupId: number | null = null;

    // Reactive state using Svelte 5 runes
    public connectionState = $state<ConnectionState>({
        status: 'disconnected',
        error: null
    });

    // THE ONE UNIVERSAL CALLBACK - called for ANY update
    public onRefreshGroup: (() => void) | null = null;
    
    // Special callback for entry highlighting
    public onEntryHighlight: ((entryId: number) => void) | null = null;

    async connect(groupId: number): Promise<void> {
        console.log('RealtimeStore: Starting connection to group', groupId);
        
        // Disconnect existing connection if any
        this.disconnect();

        this.groupId = groupId;
        this.connectionState.status = 'connecting';
        this.connectionState.error = null;

        try {
            this.manager = new RealtimeReceiptManager(groupId);
            
            // Set up event handlers
            this.manager.onConnected = () => {
                console.log('RealtimeStore: WebSocket connected');
                this.connectionState.status = 'connected';
                this.connectionState.error = null;
            };

            this.manager.onDisconnected = () => {
                console.log('RealtimeStore: WebSocket disconnected');
                this.connectionState.status = 'disconnected';
            };

            this.manager.onError = (error) => {
                console.error('RealtimeStore: WebSocket error:', error);
                this.connectionState.status = 'error';
                this.connectionState.error = error.toString();
            };

            // THE MAGIC: One message handler for everything
            this.manager.onMessage = (message) => {
                console.log('RealtimeStore: Received message type:', message.type);
                
                if (message.type === 'refresh_group') {
                    // Universal refresh for all updates
                    console.log('RealtimeStore: Refreshing group due to:', message.action || 'update');
                    if (this.onRefreshGroup) {
                        this.onRefreshGroup();
                    }
                } else if (message.type === 'entry_updated') {
                    // Special handling for entry updates (for highlighting)
                    console.log('RealtimeStore: Entry updated:', message.entry_id);
                    if (this.onEntryHighlight && message.entry_id) {
                        this.onEntryHighlight(message.entry_id);
                    }
                    // Also refresh the group
                    if (this.onRefreshGroup) {
                        this.onRefreshGroup();
                    }
                } else {
                    console.log('RealtimeStore: Unknown message type:', message.type);
                }
            };

            // Connect to WebSocket
            await this.manager.connect();
            console.log('RealtimeStore: Successfully connected to group', groupId);
        } catch (error) {
            console.error('RealtimeStore: Failed to connect:', error);
            this.connectionState.status = 'error';
            this.connectionState.error = error instanceof Error ? error.message : 'Unknown connection error';
            throw error;
        }
    }

    disconnect(): void {
        console.log('RealtimeStore: Disconnecting');
        if (this.manager) {
            this.manager.disconnect();
            this.manager = null;
        }

        this.connectionState.status = 'disconnected';
        this.connectionState.error = null;
        this.groupId = null;
    }

    // Update a receipt entry
    async updateEntry(entryId: number, assignedTo: string[]): Promise<void> {
        try {
            console.log('RealtimeStore: Updating entry', entryId, assignedTo);
            await updateReceiptEntry(entryId, assignedTo);
        } catch (error) {
            console.error('RealtimeStore: Failed to update entry:', error);
            throw error;
        }
    }

    // Getters for computed values
    get isConnected(): boolean {
        return this.connectionState.status === 'connected';
    }

    get isConnecting(): boolean {
        return this.connectionState.status === 'connecting';
    }

    get hasError(): boolean {
        return this.connectionState.status === 'error';
    }

    get statusText(): string {
        switch (this.connectionState.status) {
            case 'connected': return 'Live';
            case 'connecting': return 'Connecting...';
            case 'disconnected': return 'Offline';
            case 'error': return 'Error';
            default: return 'Unknown';
        }
    }
}

// Export a singleton instance
export const realtimeStore = new RealtimeStore();
