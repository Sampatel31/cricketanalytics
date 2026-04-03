import React, { useEffect } from 'react'
import { useAuctionStore } from '../store/auction.store'
import { relativeTime } from '../utils/format'
import { ALERT_AUTO_DISMISS_MS } from '../config/constants'
import type { Alert } from '../types/auction'
import clsx from 'clsx'

function alertIcon(type: Alert['type']): string {
  const icons: Record<string, string> = {
    overbid: '⚠️',
    archetype_gap: '🚨',
    budget: '⚠️',
    picked: '✅',
    error: '🔴',
    info: 'ℹ️',
  }
  return icons[type] ?? 'ℹ️'
}

function severityClass(severity: Alert['severity']): string {
  return clsx({
    'border-l-[#1d9e75]': severity === 'success',
    'border-l-[#ef9f27]': severity === 'warning',
    'border-l-[#d85a30]': severity === 'error',
    'border-l-[#7f77dd]': severity === 'info',
  })
}

interface AlertItemProps {
  alert: Alert
  onDismiss: (id: string) => void
}

function AlertItem({ alert, onDismiss }: AlertItemProps): React.ReactElement {
  useEffect(() => {
    if (alert.type !== 'error') {
      const timer = setTimeout(() => onDismiss(alert.id), ALERT_AUTO_DISMISS_MS)
      return () => clearTimeout(timer)
    }
    return undefined
  }, [alert.id, alert.type, onDismiss])

  return (
    <div
      className={clsx(
        'flex items-start gap-2 p-2 rounded-lg border border-[#1e1e30] border-l-2 bg-[#111120] animate-fade-in',
        severityClass(alert.severity)
      )}
      role="alert"
    >
      <span className="text-sm mt-0.5 shrink-0">{alertIcon(alert.type)}</span>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-[#e8e6df] leading-snug">{alert.message}</p>
        <p className="text-[10px] text-[#9c9a92] mt-0.5">{relativeTime(alert.timestamp)}</p>
      </div>
      <button
        onClick={() => onDismiss(alert.id)}
        aria-label="Dismiss alert"
        className="shrink-0 text-[#9c9a92] hover:text-[#e8e6df] text-sm leading-none"
      >
        ×
      </button>
    </div>
  )
}

export default function AlertsFeed(): React.ReactElement {
  const { alerts, removeAlert } = useAuctionStore()

  return (
    <div className="panel h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-[#e8e6df]">🔔 Alerts Feed</h3>
        {alerts.length > 0 && (
          <span className="text-xs text-[#9c9a92]">{alerts.length} alerts</span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto space-y-2 max-h-96">
        {alerts.length === 0 ? (
          <div className="text-center text-[#9c9a92] text-sm py-8">No alerts yet</div>
        ) : (
          alerts.map((alert) => (
            <AlertItem key={alert.id} alert={alert} onDismiss={removeAlert} />
          ))
        )}
      </div>
    </div>
  )
}
