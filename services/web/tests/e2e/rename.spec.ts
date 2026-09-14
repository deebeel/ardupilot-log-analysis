import { expect, test } from '@playwright/test';

test('кнопка перейменування є на сторінці деталей', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-good');

  // Act
  const button = page.getByTestId('rename-flight');

  // Assert
  await expect(button).toBeVisible();
});

test('кнопка перейменування є на кожній картці у списку', async ({ page }) => {
  // Arrange
  await page.goto('/');

  // Act
  const buttons = page.getByTestId('rename-flight');

  // Assert (flight-good, flight-bad, і зламаний .error.json з index.spec.ts)
  await expect(buttons).toHaveCount(3);
});

test('перейменування на сторінці деталей зберігається після перезавантаження', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-good');
  page.once('dialog', (dialog) => dialog.accept('Мій тестовий політ'));
  await page.getByTestId('rename-flight').click();

  // Act
  await page.reload();

  // Assert
  await expect(page.getByTestId('flight-title')).toContainText('Мій тестовий політ');
});

test('скасування діалогу перейменування лишає flight_id як був', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-good');
  page.once('dialog', (dialog) => dialog.dismiss());

  // Act
  await page.getByTestId('rename-flight').click();

  // Assert
  await expect(page.getByTestId('flight-title')).toContainText('flight-good');
});

test('порожнє ім\'я після перейменування повертає відображення до flight_id', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-good');
  page.once('dialog', (dialog) => dialog.accept('Custom'));
  await page.getByTestId('rename-flight').click();
  await expect(page.getByTestId('flight-title')).toContainText('Custom');

  // Act
  page.once('dialog', (dialog) => dialog.accept(''));
  await page.getByTestId('rename-flight').click();

  // Assert
  await expect(page.getByTestId('flight-title')).toContainText('flight-good');
});

test('перейменування на картці у списку теж зберігається після перезавантаження', async ({ page }) => {
  // Arrange
  await page.goto('/');
  page.once('dialog', (dialog) => dialog.accept('Перший тестовий'));

  // Act
  await page.getByTestId('rename-flight').first().click();
  await page.reload();

  // Assert
  await expect(page.getByTestId('flight-name').first()).toHaveText('Перший тестовий');
});
