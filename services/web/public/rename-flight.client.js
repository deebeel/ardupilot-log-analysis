// Перейменування польотів у списку/на сторінці деталей — суто клієнтське,
// без сервера/БД: ключ `localStorage`, тому переживає перезавантаження
// сторінки в тому самому браузері, але не бачиться іншими глядачами.
// Статичний файл (не імпорт з фронтматтера) — той самий підхід, що й для
// htmx.org: жодних браузерних globals на верхньому рівні модуля не було б
// проблемою тут, але узгодженість підходу важливіша за економію одного файлу.
(function () {
  var KEY_PREFIX = 'flightName:';

  function customName(id) {
    try {
      return localStorage.getItem(KEY_PREFIX + id);
    } catch {
      return null;
    }
  }

  function setCustomName(id, name) {
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

  function applyStoredNames() {
    document.querySelectorAll('[data-flight-name]').forEach(function (el) {
      var id = el.getAttribute('data-flight-name');
      if (!id) {
        return;
      }
      el.textContent = customName(id) || id;
    });
  }

  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-rename-flight]');
    if (!button) {
      return;
    }
    event.preventDefault();
    var id = button.getAttribute('data-rename-flight');
    if (!id) {
      return;
    }
    var next = window.prompt('Назва польоту:', customName(id) || id);
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
})();
