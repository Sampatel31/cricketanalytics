const PREFIX = 'sovereign_'

export const storage = {
  get<T>(key: string, defaultValue?: T): T | undefined {
    try {
      const item = localStorage.getItem(PREFIX + key)
      if (item === null) return defaultValue
      return JSON.parse(item) as T
    } catch {
      return defaultValue
    }
  },

  set<T>(key: string, value: T): void {
    try {
      localStorage.setItem(PREFIX + key, JSON.stringify(value))
    } catch (err) {
      console.warn('localStorage.set failed:', err)
    }
  },

  remove(key: string): void {
    localStorage.removeItem(PREFIX + key)
  },

  clear(): void {
    Object.keys(localStorage)
      .filter((k) => k.startsWith(PREFIX))
      .forEach((k) => localStorage.removeItem(k))
  },
}
