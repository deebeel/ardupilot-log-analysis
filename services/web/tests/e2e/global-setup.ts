/**
 * Playwright гарантує рівно один виклик цієї функції в головному процесі, до
 * старту будь-яких воркерів чи `webServer`. Тут — і лише тут — можна безпечно
 * чистити й засівати фікстурні теки (на відміну від `playwright.config.ts`,
 * який перевиконується в кожному воркер-процесі).
 */
import { prepareFixtures } from './fixtures.ts';

export default function globalSetup(): void {
  prepareFixtures();
}
