export type MessageCallback = (text: string, done: boolean) => void;

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private token: string;
  private onMessageCallback: MessageCallback | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private shouldReconnect = true;
  private isConnecting = false;

  constructor(sessionId: string, token: string) {
    this.sessionId = sessionId;
    this.token = token;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.isConnecting || this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      this.isConnecting = true;
      const wsBase = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001')
        .replace(/^http/, 'ws');
      const url = `${wsBase}/api/v1/ws/chat/${this.sessionId}?token=${this.token}`;

      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        resolve();
      };

      this.ws.onerror = (err) => {
        this.isConnecting = false;
        reject(err);
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string);
          if (this.onMessageCallback) {
            if (typeof data.error === 'string' && data.error.trim()) {
              this.onMessageCallback(`I hit an error while generating a response: ${data.error}`, true);
              return;
            }

            // Backend sends full assistant responses as { type: "message", content: "..." }.
            if (data.type === 'message') {
              this.onMessageCallback(data.content || '', true);
              return;
            }

            // Handle token-stream compatible payloads if used in the future.
            this.onMessageCallback(data.text || data.content || '', data.done === true);
          }
        } catch {
          if (this.onMessageCallback) {
            this.onMessageCallback(event.data as string, false);
          }
        }
      };

      this.ws.onclose = () => {
        this.isConnecting = false;
        if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          setTimeout(() => this.connect(), this.reconnectDelay * this.reconnectAttempts);
        }
      };
    });
  }

  onMessage(callback: MessageCallback): void {
    this.onMessageCallback = callback;
  }

  send(message: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ message }));
    } else {
      console.warn('WebSocket not connected. Message not sent.');
    }
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this.ws?.close();
    this.ws = null;
  }
}
