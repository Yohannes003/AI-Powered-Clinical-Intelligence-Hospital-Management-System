/**
 * WebSocket Service for real-time ICU monitoring
 * Handles connection, reconnection, and message callbacks
 */

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000";

class WebSocketService {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 2000;
    this.messageHandlers = new Map();
    this.connectionHandlers = new Map();
    this.pingInterval = null;
    this.isConnected = false;
    this.currentEndpoint = null;
  }

  connect(endpoint = "/ws/dashboard") {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.currentEndpoint = endpoint;
    const url = `${WS_URL}${endpoint}`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log(`[WebSocket] Connected to ${endpoint}`);
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this._notifyHandlers("connected", { endpoint });
        this._startPing();
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this._handleMessage(message);
        } catch (e) {
          console.error("[WebSocket] Parse error:", e);
        }
      };

      this.ws.onclose = () => {
        console.log("[WebSocket] Disconnected");
        this.isConnected = false;
        this._stopPing();
        this._notifyHandlers("disconnected", {});
        this._scheduleReconnect();
      };

      this.ws.onerror = (error) => {
        console.error("[WebSocket] Error:", error);
        this.isConnected = false;
        this._notifyHandlers("error", error);
      };
    } catch (e) {
      console.error("[WebSocket] Connection failed:", e);
      this._scheduleReconnect();
    }
  }

  disconnect() {
    this._stopPing();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
  }

  // Subscribe to message types
  on(type, callback) {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set());
    }
    this.messageHandlers.get(type).add(callback);

    // Return unsubscribe function
    return () => {
      this.messageHandlers.get(type)?.delete(callback);
    };
  }

  // Subscribe to connection events
  onConnection(callback) {
    this.connectionHandlers.set(Date.now(), callback);
    return () => this.connectionHandlers.delete(Date.now());
  }

  send(action, data = {}) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action, ...data }));
    }
  }

  // Internal: handle incoming messages
  _handleMessage(message) {
    const { type, data } = message;

    // Notify type-specific handlers
    if (this.messageHandlers.has(type)) {
      this.messageHandlers.get(type).forEach((cb) => {
        try {
          cb(data, message);
        } catch (e) {
          console.error(`[WebSocket] Handler error for ${type}:`, e);
        }
      });
    }

    // Notify wildcard handlers
    if (this.messageHandlers.has("*")) {
      this.messageHandlers.get("*").forEach((cb) => {
        try {
          cb(message);
        } catch (e) {
          console.error("[WebSocket] Wildcard handler error:", e);
        }
      });
    }
  }

  // Internal: notify connection handlers
  _notifyHandlers(event, data) {
    this.connectionHandlers.forEach((cb) => {
      try {
        cb(event, data);
      } catch (e) {
        console.error("[WebSocket] Connection handler error:", e);
      }
    });
  }

  _startPing() {
    this.pingInterval = setInterval(() => {
      this.send("ping");
    }, 30000);
  }

  _stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  _scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error("[WebSocket] Max reconnection attempts reached");
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * this.reconnectAttempts;

    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(() => {
      if (!this.isConnected && this.currentEndpoint) {
        this.connect(this.currentEndpoint);
      }
    }, delay);
  }
}

// Singleton instance
const wsService = new WebSocketService();

export default wsService;
