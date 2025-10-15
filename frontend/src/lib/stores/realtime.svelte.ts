interface WebSocketMessage {
    type: string;
    [key: string]: any;
}

interface ConnectionState {
    status: 'disconnected' | 'connecting' | 'connected' | 'error';
    error: string | null;
}

export class RealtimeStore {
    private websocket: WebSocket | null = null;
    private baseUrl: string;

    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 1000;
    private connected = false;

    private pingInterval: number | null = null;
    private lastUpdateTime = 0;
    private UPDATE_THROTTLE = 100; // ms - prevent rapid consecutive refreshes

    private groupId: number | null = null;

    // Reactive state using Svelte 5 runes
    public connectionState = $state<ConnectionState>({
        status: 'disconnected',
        error: null
    });

    // Callback for refreshing group data
    public onRefreshGroup: (() => void) | null = null;

    constructor() {
        const apiBaseUrl = import.meta.env.VITE_BACKEND_HOST || 'http://localhost:8000';
        this.baseUrl = apiBaseUrl.replace(/^http/, 'ws');
    }

    async connect(groupId: number): Promise<void> {
        return new Promise((resolve, reject) => {
            // Already connecting or connected
            if (this.connected || (this.websocket && this.websocket.readyState === WebSocket.OPEN)) {
                if (this.groupId === groupId) {
                    resolve();
                    return;
                }
            }

            // Disconnect from previous group if needed
            if (this.groupId !== groupId) {
                this.disconnect();
            }

            this.groupId = groupId;
            this.connected = true;
            this.connectionState.status = 'connecting';
            this.connectionState.error = null;

            const wsUrl = `${this.baseUrl}/ws/groups/${groupId}`;
            console.log(`RealtimeStore: Connecting to WebSocket: ${wsUrl}`);
            
            this.websocket = new WebSocket(wsUrl);

            const connectTimeout = setTimeout(() => {
                if (this.websocket && this.websocket.readyState === WebSocket.CONNECTING) {
                    this.websocket.close();
                    reject(new Error('WebSocket connection timeout'));
                }
            }, 10000);

            this.websocket.onopen = () => {
                console.log('RealtimeStore: WebSocket connected successfully');
                clearTimeout(connectTimeout);
                this.connected = false;
                this.reconnectAttempts = 0;
                this.connectionState.status = 'connected';
                this.connectionState.error = null;
                this.startPing();
                resolve();
            };

            this.websocket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data) as WebSocketMessage;
                    this.handleMessage(message);
                } catch (error) {
                    console.error('RealtimeStore: Error parsing WebSocket message:', error);
                }
            };

            this.websocket.onclose = (event) => {
                console.log('RealtimeStore: WebSocket connection closed', event.code);
                clearTimeout(connectTimeout);
                this.connected = false;
                this.stopPing();
                this.connectionState.status = 'disconnected';

                // Attempt to reconnect unless it was a clean close
                if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnect();
                } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                    this.connectionState.status = 'error';
                    this.connectionState.error = 'Max reconnection attempts reached';
                    reject(new Error('Max reconnection attempts reached'));
                }
            };

            this.websocket.onerror = (error) => {
                console.error('RealtimeStore: WebSocket error:', error);
                clearTimeout(connectTimeout);
                this.connected = false;
                this.connectionState.status = 'error';
                this.connectionState.error = 'Connection error';
                reject(error);
            };
        });
    }

    disconnect(): void {
        console.log('RealtimeStore: Disconnecting');
        this.stopPing();
        
        if (this.websocket) {
            this.websocket.close(1000, 'Client disconnecting');
            this.websocket = null;
        }

        this.connectionState.status = 'disconnected';
        this.connectionState.error = null;
        this.groupId = null;
        this.reconnectAttempts = 0;
    }

    private reconnect(): void {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('RealtimeStore: Max reconnection attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        
        console.log(`RealtimeStore: Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
        
        setTimeout(() => {
            if (this.groupId !== null) {
                this.connect(this.groupId).catch((error) => {
                    console.error('RealtimeStore: Reconnection failed:', error);
                });
            }
        }, delay);
    }

    private startPing(): void {
        this.pingInterval = window.setInterval(() => {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({
                    type: 'ping',
                    timestamp: Date.now()
                }));
            }
        }, 30000); // Every 30 seconds
    }

    private stopPing(): void {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    private handleMessage(message: WebSocketMessage): void {
        console.log('RealtimeStore: Received message type:', message.type);

        switch (message.type) {
            case 'connected':
                console.log(`RealtimeStore: Connected to group ${message.group_id}`);
                break;

            case 'pong':
                // Connection is alive, no action needed
                break;

            case 'refresh_group':
                // Throttle refreshes to prevent rapid consecutive updates
                const now = Date.now();
                if (now - this.lastUpdateTime > this.UPDATE_THROTTLE) {
                    this.lastUpdateTime = now;
                    console.log('RealtimeStore: Refreshing group due to:', message.action || 'update');
                    if (this.onRefreshGroup) {
                        this.onRefreshGroup();
                    }
                } else {
                    console.log('RealtimeStore: Skipping refresh (throttled)');
                }
                break;

            case 'error':
                console.error('RealtimeStore: Server error:', message.message);
                break;

            default:
                console.log('RealtimeStore: Unknown message type:', message.type);
        }
    }

    // Computed getters
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

    get currentGroupId(): number | null {
        return this.groupId;
    }
}

export const realtimeStore = new RealtimeStore();
