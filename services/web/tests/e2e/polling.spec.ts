/**
 * Сценарії (TEST-PLAN, htmx-поллінг індексної сторінки):
 * 1. Порожня `live`-тека на старті → нічого крім порожнього стану.
 * 2. Новий JSON з'являється в теці ПІСЛЯ відкриття сторінки → картка з'являється
 *    сама, без `page.reload()`.
 * 3. Обгортка з `hx-*` атрибутами лишається на місці й після одного циклу свапу
 *    (перевіряє граничний випадок outerHTML-заміни: якщо партиал повертає розмітку
 *    БЕЗ обгортки, поллінг зупиняється на першому оновленні — тут це не так).
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

test('поллінг-обгортка лишається на місці після циклу оновлення (не зникає після outerHTML-свапу)', async ({ page }) => {
  // Arrange
  await page.goto('/');
  const poller = page.getByTestId('flight-list-poller');
  await expect(poller).toHaveAttribute('hx-get', '/partials/flight-list');

  // Act
  addLiveFlight('flight-triggers-a-swap');
  await expect(page.getByRole('link', { name: 'flight-triggers-a-swap' })).toBeVisible({ timeout: 3_000 });

  // Assert
  await expect(poller).toHaveAttribute('hx-get', '/partials/flight-list');
});
