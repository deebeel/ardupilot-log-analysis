import { expect, test } from '@playwright/test';

test('список показує всі польоти з теки результатів', async ({ page }) => {
  // Arrange
  await page.goto('/');

  // Act
  const cards = page.getByTestId('flight-card');

  // Assert
  await expect(cards).toHaveCount(4);
});

test('кожен політ у списку — посилання на свою сторінку звіту', async ({ page }) => {
  // Arrange
  await page.goto('/');

  // Act
  const link = page.getByRole('link', { name: 'flight-good' });

  // Assert
  await expect(link).toHaveAttribute('href', '/flight/flight-good');
});

test('політ із .error.json лишається у списку та позначений як помилка', async ({ page }) => {
  // Arrange
  await page.goto('/');

  // Act
  const badge = page.getByTestId('flight-card').filter({ hasText: 'flight-broken' }).getByTestId('error-badge');

  // Assert
  await expect(badge).toBeVisible();
});

test('проміжний файл .json.tmp не потрапляє у список', async ({ page }) => {
  // Arrange
  await page.goto('/');

  // Act
  const partial = page.getByTestId('flight-card').filter({ hasText: 'flight-partial' });

  // Assert
  await expect(partial).toHaveCount(0);
});
