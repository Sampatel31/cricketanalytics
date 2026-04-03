import { formatCurrency, formatPct, relativeTime } from '../format'

describe('format utils', () => {
  it('formats currency', () => {
    expect(formatCurrency(16)).toBe('₹16.0Cr')
    expect(formatCurrency(4.4)).toBe('₹4.4Cr')
  })

  it('formats percentage', () => {
    expect(formatPct(5.0)).toBe('+5.0%')
    expect(formatPct(-3.2)).toBe('-3.2%')
  })

  it('formats relative time', () => {
    const now = new Date().toISOString()
    expect(relativeTime(now)).toMatch(/\d+s ago/)
  })
})
