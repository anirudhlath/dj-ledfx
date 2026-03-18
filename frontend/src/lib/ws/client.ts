/**
 * Multiplexed WebSocket client with auto-reconnect and binary frame parsing.
 */

type JsonMessage = {
  channel: string;
  [key: string]: unknown;
};

type FrameMessage = {
  deviceName: string;
  seq: number;
  rgb: Uint8Array;
};

type MessageHandler = (msg: JsonMessage) => void;
type FrameHandler = (frame: FrameMessage) => void;

export class WsClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectDelay = 100;
  private maxReconnectDelay = 5000;
  private cmdId = 0;
  private handlers = new Map<string, Set<MessageHandler>>();
  private frameHandlers = new Set<FrameHandler>();
  private pendingAcks = new Map<number, { resolve: (v: JsonMessage) => void; reject: (e: Error) => void }>();
  private lastBeatSub: { fps: number } | null = null;
  private lastFrameSub: { fps: number; devices: string[] } | null = null;
  private _connected = false;
  private shouldReconnect = true;

  constructor(url?: string) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.url = url || `${protocol}//${window.location.host}/ws`;
  }

  get connected(): boolean {
    return this._connected;
  }

  connect(): void {
    this.shouldReconnect = true;
    this._connect();
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this.ws?.close();
    this.ws = null;
    this._connected = false;
  }

  private _connect(): void {
    try {
      this.ws = new WebSocket(this.url);
      this.ws.binaryType = 'arraybuffer';

      this.ws.onopen = () => {
        this._connected = true;
        this.reconnectDelay = 100;
        // Re-send subscriptions on reconnect
        if (this.lastBeatSub) {
          this.subscribeBeat(this.lastBeatSub.fps);
        }
        if (this.lastFrameSub) {
          this.subscribeFrames(this.lastFrameSub.fps, this.lastFrameSub.devices);
        }
      };

      this.ws.onclose = () => {
        this._connected = false;
        if (this.shouldReconnect) {
          setTimeout(() => this._connect(), this.reconnectDelay);
          this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
        }
      };

      this.ws.onerror = () => {
        // onclose will fire after this
      };

      this.ws.onmessage = (event: MessageEvent) => {
        if (event.data instanceof ArrayBuffer) {
          this._handleBinary(event.data);
        } else {
          this._handleJson(event.data as string);
        }
      };
    } catch {
      if (this.shouldReconnect) {
        setTimeout(() => this._connect(), this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
      }
    }
  }

  private _handleJson(data: string): void {
    try {
      const msg = JSON.parse(data) as JsonMessage;
      const channel = msg.channel;

      // Handle ack/error correlation
      if ((channel === 'ack' || channel === 'error') && typeof msg.id === 'number') {
        const pending = this.pendingAcks.get(msg.id);
        if (pending) {
          this.pendingAcks.delete(msg.id);
          if (channel === 'error') {
            pending.reject(new Error(msg.detail as string));
          } else {
            pending.resolve(msg);
          }
        }
      }

      // Dispatch to channel handlers
      const handlers = this.handlers.get(channel);
      if (handlers) {
        for (const handler of handlers) {
          handler(msg);
        }
      }
    } catch {
      // Ignore parse errors
    }
  }

  private _handleBinary(data: ArrayBuffer): void {
    const view = new DataView(data);
    if (data.byteLength < 6) return;

    // Binary frame format: [2B name_len LE][N name UTF-8][4B seq LE][RGB data]
    const nameLen = view.getUint16(0, true);
    if (data.byteLength < 2 + nameLen + 4) return;

    const nameBytes = new Uint8Array(data, 2, nameLen);
    const deviceName = new TextDecoder().decode(nameBytes);
    const seq = view.getUint32(2 + nameLen, true);
    const rgb = new Uint8Array(data, 2 + nameLen + 4);

    const frame: FrameMessage = { deviceName, seq, rgb };
    for (const handler of this.frameHandlers) {
      handler(frame);
    }
  }

  on(channel: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(channel)) {
      this.handlers.set(channel, new Set());
    }
    this.handlers.get(channel)!.add(handler);
    return () => this.handlers.get(channel)?.delete(handler);
  }

  onFrame(handler: FrameHandler): () => void {
    this.frameHandlers.add(handler);
    return () => this.frameHandlers.delete(handler);
  }

  async sendCommand(action: string, params: Record<string, unknown> = {}): Promise<JsonMessage> {
    const id = ++this.cmdId;
    const msg = { action, id, ...params };

    return new Promise((resolve, reject) => {
      this.pendingAcks.set(id, { resolve, reject });
      this.ws?.send(JSON.stringify(msg));

      // Timeout after 5s
      setTimeout(() => {
        if (this.pendingAcks.has(id)) {
          this.pendingAcks.delete(id);
          reject(new Error(`Command ${action} timed out`));
        }
      }, 5000);
    });
  }

  subscribeBeat(fps: number = 10): void {
    this.lastBeatSub = { fps };
    if (this._connected) {
      this.sendCommand('subscribe_beat', { fps }).catch(() => {});
    }
  }

  subscribeFrames(fps: number = 10, devices: string[] = []): void {
    this.lastFrameSub = { fps, devices };
    if (this._connected) {
      this.sendCommand('subscribe_frames', { fps, devices }).catch(() => {});
    }
  }
}

// Singleton instance
export const wsClient = new WsClient();
