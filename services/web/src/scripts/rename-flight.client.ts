/**
 * Перейменування польотів у списку/на сторінці деталей — суто клієнтське,
 * без сервера/БД: ключ `localStorage`, тому переживає перезавантаження
 * сторінки в тому самому браузері, але не бачиться іншими глядачами.
 *
 * Завантажується як звичайний (не `type="module"`-ізольований від помилок)
 * локальний `<script>` з `Base.astro` — Astro/Vite бандлить і типізує його як
 * будь-який інший TS-файл у проєкті, на відміну від `public/`.
 */

const KEY_PREFIX = 'flightName:';

function customName(id: string): string | null {
  try {
    return localStorage.getItem(KEY_PREFIX + id);
  } catch {
    return null;
  }
}

function setCustomName(id: string, name: string): void {
  try {
    if (name) {
      localStorage.setItem(KEY_PREFIX + id, name);
    } else {
      localStorage.removeItem(KEY_PREFIX + id);
    }
  } catch {
    // localStorage недоступний (приватний режим тощо) — перейменування без збереження
  }
}

function applyStoredNames(): void {
  document.querySelectorAll<HTMLElement>('[data-flight-name]').forEach((el) => {
    const id = el.getAttribute('data-flight-name');
    if (!id) {
      return;
    }
    el.textContent = customName(id) || id;
  });
}

document.addEventListener('click', (event) => {
  const target = event.target;
  if (!(target instanceof Element)) {
    return;
  }
  const button = target.closest<HTMLElement>('[data-rename-flight]');
  if (!button) {
    return;
  }
  event.preventDefault();
  const id = button.getAttribute('data-rename-flight');
  if (!id) {
    return;
  }
  const next = window.prompt('Назва польоту:', customName(id) || id);
  if (next === null) {
    return;
  }
  setCustomName(id, next.trim());
  applyStoredNames();
});

// Список оновлюється поллінгом (htmx outerHTML-свап) — застосувати збережені
// назви й після кожного свапу, не лише на початковому рендері.
document.body.addEventListener('htmx:afterSwap', applyStoredNames);
applyStoredNames();
