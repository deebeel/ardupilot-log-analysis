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

test.describe('3 окремі таблиці метрик — по одній на roll/pitch/yaw', () => {
  for (const axis of ['roll', 'pitch', 'yaw']) {
    test(`таблиця ${axis} показує рядок для кожної метрики з розбивкою по осях`, async ({ page }) => {
      // Arrange
      await page.goto('/flight/flight-good');

      // Act
      const rows = page.getByTestId(`metrics-table-${axis}`).locator('tbody tr');

      // Assert (corrections_per_min, mean_amplitude, mean_jerk, oscillation_time_pct)
      await expect(rows).toHaveCount(4);
    });
  }

  test('скалярна метрика (reaction_latency_ms) показана окремо, не в жодній з таблиць осей', async ({ page }) => {
    // Arrange
    await page.goto('/flight/flight-good');

    // Act
    const scalar = page.getByTestId('scalar-metric');

    // Assert
    await expect(scalar).toContainText('reaction_latency_ms');
  });
});

test.describe('дискретна кількість корекцій', () => {
  // Playwright не має test.each — параметризація тут — генерація тестів у
  // циклі на рівні модуля (ідіоматичний спосіб для Playwright), не циклом
  // усередині тіла одного тесту.
  const CASES: [string, number][] = [
    ['roll', 7],
    ['pitch', 5],
    ['yaw', 1],
  ];

  for (const [axis, expected] of CASES) {
    test(`колонка "кількість" для corrections_per_min/${axis}`, async ({ page }) => {
      // Arrange
      await page.goto('/flight/flight-good');

      // Act
      const cell = page.getByTestId(`count-corrections_per_min-${axis}`);

      // Assert
      await expect(cell).toHaveText(String(expected));
    });
  }

  test('для метрик, відмінних від corrections_per_min, колонка порожня', async ({ page }) => {
    // Arrange
    await page.goto('/flight/flight-good');

    // Act
    const cell = page.getByTestId('count-mean_amplitude-roll');

    // Assert
    await expect(cell).toHaveText('—');
  });
});

test.describe('crashed переважає всі числові пороги', () => {
  test('політ з crashed=true отримує вердикт crashed навіть із хорошими метриками', async ({ page }) => {
    // Arrange
    await page.goto('/flight/flight-crashed');

    // Act
    const verdict = page.getByTestId('verdict');

    // Assert
    await expect(verdict).toHaveAttribute('data-verdict', 'crashed');
  });

  test('картка crashed-польоту у списку показує бейдж crashed', async ({ page }) => {
    // Arrange
    await page.goto('/');

    // Act
    const card = page.getByTestId('flight-card').filter({ hasText: 'flight-crashed' });
    const badge = card.getByTestId('verdict-badge');

    // Assert
    await expect(badge).toHaveAttribute('data-verdict', 'crashed');
  });
});

test.describe('крок слайдера порогів — 1 для дискретних метрик, "any" для неперервних', () => {
  test('corrections_per_min: крок слайдера = 1', async ({ page }) => {
    // Arrange
    await page.goto('/flight/flight-good');

    // Act
    const slider = page.getByTestId('th-corrections_per_min-good_max');

    // Assert
    await expect(slider).toHaveAttribute('step', '1');
  });

  test('reaction_latency_ms: крок слайдера = 1', async ({ page }) => {
    // Arrange
    await page.goto('/flight/flight-good');

    // Act
    const slider = page.getByTestId('th-reaction_latency_ms-good_max');

    // Assert
    await expect(slider).toHaveAttribute('step', '1');
  });

  test('mean_amplitude (неперервна): крок слайдера = "any"', async ({ page }) => {
    // Arrange
    await page.goto('/flight/flight-good');

    // Act
    const slider = page.getByTestId('th-mean_amplitude-good_max');

    // Assert
    await expect(slider).toHaveAttribute('step', 'any');
  });
});

test.describe('reset-view на графіках', () => {
  test('кнопка "скинути масштаб" присутня на обох графіках', async ({ page }) => {
    // Arrange
    await page.goto('/flight/flight-good');

    // Act
    const buttons = page.getByTestId('chart-reset-view');

    // Assert
    await expect(buttons).toHaveCount(2);
  });

  test('клік на "скинути масштаб" не ламає сторінку', async ({ page }) => {
    // Arrange
    await page.goto('/flight/flight-good');

    // Act
    await page.getByTestId('chart-reset-view').first().click();

    // Assert
    await expect(page.getByTestId('stick-chart').locator('canvas').first()).toBeVisible();
  });
});
