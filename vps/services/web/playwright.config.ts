import { defineConfig, devices } from '@playwright/test';
import { fixtureDirs } from './tests/e2e/fixtures.ts';

// Три теки: з польотами, порожня і "жива" (для поллінг-тестів) — кожному сценарію
// потрібен окремий реальний сервер, а не мок. `fixtureDirs()` лише повертає шляхи,
// без побічних ефектів — цей модуль перевиконується в кожному воркер-процесі, тож
// саму підготовку файлів робить `global-setup.ts` (гарантовано один раз).
const dirs = fixtureDirs();

const POPULATED_PORT = 4331;
const EMPTY_PORT = 4332;
const LIVE_PORT = 4333;

const server = (port: number, resultsDir: string) => ({
  command: 'node ./dist/server/entry.mjs',
  url: `http://127.0.0.1:${port}/`,
  reuseExistingServer: false,
  timeout: 60_000,
  env: { RESULTS_DIR: resultsDir, HOST: '127.0.0.1', PORT: String(port) },
});

export default defineConfig({
  testDir: './tests/e2e',
  globalSetup: './tests/e2e/global-setup.ts',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [['list']],
  webServer: [
    server(POPULATED_PORT, dirs.populated),
    server(EMPTY_PORT, dirs.empty),
    server(LIVE_PORT, dirs.live),
  ],
  projects: [
    {
      name: 'populated',
      testIgnore: [/empty\.spec\.ts/, /polling\.spec\.ts/],
      use: { ...devices['Desktop Chrome'], baseURL: `http://127.0.0.1:${POPULATED_PORT}` },
    },
    {
      name: 'empty',
      testMatch: /empty\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], baseURL: `http://127.0.0.1:${EMPTY_PORT}` },
    },
    {
      // Приватна порожня-на-старті тека: поллінг-тести самі дописують у неї файли
      // під час прогону, тож ділити її з `populated` не можна (той сервер читають
      // паралельно інші тести, спільний мутабельний стан дав би нестабільні лічильники).
      name: 'live',
      testMatch: /polling\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], baseURL: `http://127.0.0.1:${LIVE_PORT}` },
    },
  ],
});
