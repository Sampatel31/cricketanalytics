import { WS_URL, WS_HEARTBEAT_INTERVAL, WS_MAX_RECONNECT_ATTEMPTS, WS_MAX_RECONNECT_DELAY_MS } from '../config/constants'
import type { WSMessage } from '../types/api'

type EventHandler = (data: Record<string, unknown>) => void

export class WebSocketClient {
  private url: string
  private sessionId: string
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts: number
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private handlers: Map<string, EventHandler[]> = new Map()
  private isDestroyed = false

  constructor(sessionId: string) {
    this.sessionId = sessionId
    this.url = `${WS_URL}/ws/${sessionId}`
    this.maxReconnectAttempts = WS_MAX_RECONNECT_ATTEMPTS
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.isDestroyed) {
        reject(new Error('WebSocketClient has been destroyed'))
        return
      }

      try {
        this.ws = new WebSocket(this.url)

        this.ws.onopen = () => {
          this.reconnectAttempts = 0
          this.startHeartbeat()
          this.emit('connected', {})
          resolve()
        }

        this.ws.onmessage = (event: MessageEvent) => {
          try {
            const message: WSMessage = JSON.parse(event.data as string)
            this.emit(message.type, message.data ?? {})
          } catch (err) {
            console.error('Failed to parse WebSocket message:', err)
          }
        }

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error)
          this.emit('error', { error: String(error) })
          reject(error)
        }

        this.ws.onclose = () => {
          this.stopHeartbeat()
          this.emit('disconnected', {})
          if (!this.isDestroyed) {
            this.scheduleReconnect()
          }
        }
      } catch (err) {
        reject(err)
      }
    })
  }

  disconnect(): void {
    this.isDestroyed = true
    this.stopHeartbeat()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  send(message: WSMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    }
  }

  on(event: string, handler: EventHandler): void {
    const existing = this.handlers.get(event) ?? []
    this.handlers.set(event, [...existing, handler])
  }

  removeListener(event: string, handler: EventHandler): void {
    const existing = this.handlers.get(event) ?? []
    this.handlers.set(event, existing.filter((h) => h !== handler))
  }

  private emit(event: string, data: Record<string, unknown>): void {
    const handlers = this.handlers.get(event) ?? []
    handlers.forEach((h) => {
      try {
        h(data)
      } catch (err) {
        console.error('Handler error for WebSocket event:', err)
      }
    })
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: 'heartbeat', data: { timestamp: Date.now() } })
    }, WS_HEARTBEAT_INTERVAL)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.emit('max_reconnect_exceeded', {})
      return
    }
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), WS_MAX_RECONNECT_DELAY_MS)
    this.reconnectAttempts++
    this.emit('reconnecting', { attempt: this.reconnectAttempts, delay })
    this.reconnectTimer = setTimeout(() => {
      if (!this.isDestroyed) {
        this.connect().catch(() => {
          // scheduleReconnect will be called by onclose
        })
      }
    }, delay)
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}
