import { expect, test } from '@playwright/test';
import { waitForHydration } from './helpers.ts';

test('політ у межах порогів отримує вердикт good на дефолтних порогах', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-good');

  // Act
  const verdict = page.getByTestId('verdict');

  // Assert
  await expect(verdict).toHaveAttribute('data-verdict', 'good');
});

test('політ поза порогами отримує вердикт bad на дефолтних порогах', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-bad');

  // Act
  const verdict = page.getByTestId('verdict');

  // Assert
  await expect(verdict).toHaveAttribute('data-verdict', 'bad');
});

test('зниження good_max слайдером погіршує вердикт', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-good');
  await waitForHydration(page);

  // Act
  await page.getByTestId('th-mean_jerk-good_max').fill('0');

  // Assert
  await expect(page.getByTestId('verdict')).toHaveAttribute('data-verdict', 'warning');
});

test('перерахунок вердикту відбувається без перезавантаження сторінки', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-good');
  await waitForHydration(page);
  await page.evaluate(() => {
    (window as unknown as { __marker: string }).__marker = 'alive';
  });

  // Act
  await page.getByTestId('th-mean_jerk-good_max').fill('0');
  await expect(page.getByTestId('verdict')).toHaveAttribute('data-verdict', 'warning');

  // Assert
  expect(await page.evaluate(() => (window as unknown as { __marker?: string }).__marker)).toBe(
    'alive',
  );
});

test('кнопка скидання повертає початковий вердикт', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-good');
  await waitForHydration(page);
  await page.getByTestId('th-mean_jerk-good_max').fill('0');
  await expect(page.getByTestId('verdict')).toHaveAttribute('data-verdict', 'warning');

  // Act
  await page.getByTestId('reset-thresholds').click();

  // Assert
  await expect(page.getByTestId('verdict')).toHaveAttribute('data-verdict', 'good');
});

test('підняття warn_max слайдером пом’якшує вердикт поганого політу', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-bad');
  await waitForHydration(page);

  // Act
  await page.getByTestId('th-mean_jerk-warn_max').fill('3.6');

  // Assert
  await expect(page.getByTestId('verdict')).toHaveAttribute('data-verdict', 'warning');
});

test('таблиця причин показує рядок для кожної осі кожної метрики', async ({ page }) => {
  // Arrange
  await page.goto('/flight/flight-good');

  // Act
  const rows = page.getByTestId('reasons-table').locator('tbody tr');

  // Assert
  await expect(rows).toHaveCount(13);
});
