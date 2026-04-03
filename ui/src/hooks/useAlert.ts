import { useCallback } from 'react'
import { useAuctionStore } from '../store/auction.store'
import type { Alert } from '../types/auction'
import { ALERT_AUTO_DISMISS_MS } from '../config/constants'

function generateId(): string {
  return Math.random().toString(36).slice(2, 11)
}

export function useAlert() {
  const { addAlert, removeAlert } = useAuctionStore()

  const showAlert = useCallback(
    (
      message: string,
      type: Alert['type'] = 'info',
      severity: Alert['severity'] = 'info',
      autoDismiss = true
    ) => {
      const id = generateId()
      const alert: Alert = {
        id,
        type,
        message,
        severity,
        timestamp: new Date().toISOString(),
      }
      addAlert(alert)
      if (autoDismiss && type !== 'error') {
        setTimeout(() => removeAlert(id), ALERT_AUTO_DISMISS_MS)
      }
      return id
    },
    [addAlert, removeAlert]
  )

  return { showAlert }
}
