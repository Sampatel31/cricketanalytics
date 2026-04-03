export function formatCurrency(value: number, decimals = 1): string {
  return `₹${value.toFixed(decimals)}Cr`
}

export function formatPct(value: number, decimals = 1): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}%`
}

export function formatNumber(value: number, decimals = 2): string {
  return value.toFixed(decimals)
}

export function formatAge(age: number): string {
  return `${age} yrs`
}

export function relativeTime(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ago`
}
