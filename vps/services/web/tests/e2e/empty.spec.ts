import { expect, test } from '@playwright/test';

test('порожня тека результатів віддає сторінку зі станом «немає польотів», а не помилку', async ({
  page,
}) => {
  // Arrange
  const url = '/';

  // Act
  const response = await page.goto(url);

  // Assert
  expect(response?.status()).toBe(200);
});

test('на порожній теці показується пояснювальний порожній стан', async ({ page }) => {
  // Arrange
  await page.goto('/');

  // Act
  const emptyState = page.getByTestId('empty-state');

  // Assert
  await expect(emptyState).toBeVisible();
});
