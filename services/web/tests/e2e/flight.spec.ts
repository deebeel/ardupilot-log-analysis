import { expect, test } from '@playwright/test';

test('сторінка існуючого політу показує його flight_id у заголовку', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-good');

  // Act
  const title = page.getByTestId('flight-title');

  // Assert
  await expect(title).toContainText('flight-good');
});

test('невалідний id у URL дає 404', async ({ request }) => {
  // Arrange
  const url = '/flight/..%2Fsecret';

  // Act
  const response = await request.get(url, { maxRedirects: 0 });

  // Assert
  expect(response.status()).toBe(404);
});

test('id із крапкою (спроба дістати сусідній файл) дає 404', async ({ request }) => {
  // Arrange
  const url = '/flight/flight-good.error';

  // Act
  const response = await request.get(url);

  // Assert
  expect(response.status()).toBe(404);
});

test('неіснуючий, але валідний id дає 404', async ({ request }) => {
  // Arrange
  const url = '/flight/flight-zzz';

  // Act
  const response = await request.get(url);

  // Assert
  expect(response.status()).toBe(404);
});

test('політ із .error.json рендериться як сторінка помилки, а не 500', async ({ request }) => {
  // Arrange
  const url = '/flight/flight-broken';

  // Act
  const response = await request.get(url);

  // Assert
  expect(response.status()).toBe(200);
});

test('сторінка зламаного політу показує текст помилки парсингу', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-broken');

  // Act
  const box = page.getByTestId('flight-error');

  // Assert
  await expect(box).toContainText('DFReader');
});

test('графік стіків поверх attitude рендериться у canvas', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-good');

  // Act
  const canvas = page.getByTestId('stick-chart').locator('canvas');

  // Assert
  await expect(canvas.first()).toBeVisible();
});

test('гістограма амплітуд рендериться у canvas', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-good');

  // Act
  const canvas = page.getByTestId('amplitude-histogram').locator('canvas');

  // Assert
  await expect(canvas.first()).toBeVisible();
});
