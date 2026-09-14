/**
 * Кастомні назви польотів — суто клієнтське, `localStorage`, без сервера/БД.
 * Приватне для одного браузера (узгоджене обмеження, не недогляд).
 */

const KEY_PREFIX = 'flightName:';

export function getStoredName(flightId: string): string | null {
  try {
    return localStorage.getItem(KEY_PREFIX + flightId);
  } catch {
    return null;
  }
}

export function setStoredName(flightId: string, name: string): void {
  try {
    if (name) {
      localStorage.setItem(KEY_PREFIX + flightId, name);
    } else {
      localStorage.removeItem(KEY_PREFIX + flightId);
    }
  } catch {
    // localStorage недоступний (приватний режим тощо) — перейменування без збереження
  }
}
