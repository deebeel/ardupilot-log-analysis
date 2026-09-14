/**
 * Сценарії (TEST-PLAN, React-поллінг індексної сторінки — `fetch('/api/flights')`
 * раз на секунду, без htmx):
 * 1. Порожня `live`-тека на старті → нічого крім порожнього стану.
 * 2. Новий JSON з'являється в теці ПІСЛЯ відкриття сторінки → картка з'являється
 *    сама, без `page.reload()`.
 * 3. Поллінг триває довше одного тика — другий політ, доданий пізніше, теж
 *    з'являється сам (перевіряє, що `setInterval` не зупиняється після першого
 *    оновлення, на відміну від одноразового `setTimeout`).
 */
import { expect, test } from '@playwright/test';
import { addLiveFlight } from './fixtures.ts';

// Тести цього файла накопичують стан у спільній `live`-теці (кожен наступний додає
// файл поверх попередніх) — тому виконуються послідовно в одному воркері, а не
// паралельно, як дозволяє глобальний `fullyParallel`.
test.describe.configure({ mode: 'serial' });

test('порожня live-тека на старті показує порожній стан', async ({ page }) => {
  // Arrange
  await page.goto('/');

  // Act
  const emptyState = page.getByTestId('empty-state');

  // Assert
  await expect(emptyState).toBeVisible();
});

test('новий політ у теці з\'являється в списку сам, без перезавантаження сторінки', async ({ page }) => {
  // Arrange
  await page.goto('/');
  const link = page.getByRole('link', { name: 'flight-appeared-live' });
  await expect(link).toHaveCount(0);

  // Act
  addLiveFlight('flight-appeared-live');

  // Assert
  await expect(link).toBeVisible({ timeout: 3_000 });
});

test('поллінг триває й після першого оновлення — другий пізніший політ теж з\'являється сам', async ({ page }) => {
  // Arrange
  await page.goto('/');
  const first = page.getByRole('link', { name: 'flight-triggers-poll-1' });

  // Act
  addLiveFlight('flight-triggers-poll-1');
  await expect(first).toBeVisible({ timeout: 3_000 });
  addLiveFlight('flight-triggers-poll-2');

  // Assert
  await expect(page.getByRole('link', { name: 'flight-triggers-poll-2' })).toBeVisible({ timeout: 3_000 });
});
