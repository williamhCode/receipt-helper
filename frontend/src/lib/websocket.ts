// src/lib/websocket.ts

export interface WebSocketMessage {
    type: string;
    [key: string]: any;
}

export class RealtimeReceiptManager {
    private websocket: WebSocket | null = null;
    private groupId: number;
    private baseUrl: string;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 1000;
    private isConnecting = false;
    private pingInterval: number | null = null;

    // Simple event callbacks
    public onConnected: (() => void) | null = null;
    public onDisconnected: (() => void) | null = null;
    public onError: ((error: Event) => void) | null = null;
    public onMessage: ((message: WebSocketMessage) => void) | null = null;

    constructor(groupId: number, baseUrl?: string) {
        this.groupId = groupId;

        const apiBaseUrl = import.meta.env.VITE_BACKEND_HOST || 'http://localhost:8000';
        this.baseUrl = baseUrl || apiBaseUrl.replace(/^http/, 'ws');
    }

    async connect(): Promise<void> {
        return new Promise((resolve, reject) => {
            if (this.isConnecting || (this.websocket && this.websocket.readyState === WebSocket.OPEN)) {
                resolve();
                return;
            }

            this.isConnecting = true;
            const wsUrl = `${this.baseUrl}/ws/groups/${this.groupId}`;
            
            console.log(`Connecting to WebSocket: ${wsUrl}`);
            this.websocket = new WebSocket(wsUrl);

            const connectTimeout = setTimeout(() => {
                if (this.websocket && this.websocket.readyState === WebSocket.CONNECTING) {
                    this.websocket.close();
                    reject(new Error('WebSocket connection timeout'));
                }
            }, 10000);

            this.websocket.onopen = () => {
                console.log('WebSocket connected successfully');
                clearTimeout(connectTimeout);
                this.isConnecting = false;
                this.reconnectAttempts = 0;
                
                if (this.onConnected) {
                    this.onConnected();
                }

                this.startPing();
                resolve();
            };

            this.websocket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data) as WebSocketMessage;
                    this.handleMessage(message);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };

            this.websocket.onclose = (event) => {
                console.log('WebSocket connection closed', event.code);
                clearTimeout(connectTimeout);
                this.isConnecting = false;
                this.stopPing();
                
                if (this.onDisconnected) {
                    this.onDisconnected();
                }

                // Attempt to reconnect unless it was a clean close
                if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnect();
                } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                    reject(new Error('Max reconnection attempts reached'));
                }
            };

            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                clearTimeout(connectTimeout);
                this.isConnecting = false;
                
                if (this.onError) {
                    this.onError(error);
                }
                
                reject(error);
            };
        });
    }

    disconnect(): void {
        this.stopPing();
        if (this.websocket) {
            this.websocket.close(1000, 'Client disconnecting');
            this.websocket = null;
        }
    }

    private reconnect(): void {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        
        console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
        
        setTimeout(() => {
            this.connect().catch((error) => {
                console.error('Reconnection failed:', error);
            });
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
        }, 30000);
    }

    private stopPing(): void {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    private handleMessage(message: WebSocketMessage): void {
        console.log('Received WebSocket message:', message.type);

        // Call the message handler
        if (this.onMessage) {
            this.onMessage(message);
        }

        // Built-in handling for connection messages
        switch (message.type) {
            case 'connected':
                console.log(`Connected to group ${message.group_id}`);
                break;
            case 'pong':
                // Connection is alive
                break;
            case 'error':
                console.error('Server error:', message.message);
                break;
        }
    }

    // Get connection status
    get isConnected(): boolean {
        return this.websocket?.readyState === WebSocket.OPEN;
    }

    get connectionState(): string {
        if (!this.websocket) return 'disconnected';
        
        switch (this.websocket.readyState) {
            case WebSocket.CONNECTING: return 'connecting';
            case WebSocket.OPEN: return 'connected';
            case WebSocket.CLOSING: return 'closing';
            case WebSocket.CLOSED: return 'disconnected';
            default: return 'unknown';
        }
    }
}
