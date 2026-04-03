export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
export const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000'
export const LOG_LEVEL = import.meta.env.VITE_LOG_LEVEL ?? 'info'

export const WS_HEARTBEAT_INTERVAL = 30_000
export const WS_MAX_RECONNECT_ATTEMPTS = 10
export const ALERT_AUTO_DISMISS_MS = 5_000
export const BUDGET_DEFAULT = 100
export const SQUAD_SIZE = 25
