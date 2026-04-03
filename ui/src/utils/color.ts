export const ARCHETYPE_COLORS: Record<string, string> = {
  FSH: '#7f77dd',
  AGA: '#1d9e75',
  PRB: '#ef9f27',
  CON: '#3b82f6',
  FIN: '#d85a30',
  ALL: '#06b6d4',
  SPC: '#8b5cf6',
  UNK: '#9c9a92',
}

export function archetypeColor(code: string): string {
  return ARCHETYPE_COLORS[code] ?? ARCHETYPE_COLORS['UNK']
}

export function dnaMatchColor(pct: number): string {
  if (pct >= 80) return '#1d9e75'
  if (pct >= 60) return '#ef9f27'
  return '#d85a30'
}
