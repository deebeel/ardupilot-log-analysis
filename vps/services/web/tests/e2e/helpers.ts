import { expect, type Page } from '@playwright/test';

/**
 * Чекає, поки Astro-острови гідратуються.
 *
 * До гідратації розмітка вже є (SSR), але обробники React ще не навішані — ввід у слайдер
 * тоді просто губиться. Astro знімає атрибут `ssr` з <astro-island> після гідратації.
 * Логіка очікування живе тут, а не в тілі тесту (жодних управляючих конструкцій у тестах).
 */
export async function waitForHydration(page: Page): Promise<void> {
  await page.locator('astro-island').first().waitFor({ state: 'attached' });
  await expect(page.locator('astro-island[ssr]')).toHaveCount(0);
}
