import { defineConfig, devices } from '@playwright/test';
import { prepareFixtures } from './tests/e2e/fixtures.ts';

// Дві теки: з польотами і порожня — для сценарію «порожня тека результатів»
// потрібен окремий реальний сервер, а не мок.
const dirs = prepareFixtures();

const POPULATED_PORT = 4331;
const EMPTY_PORT = 4332;

const server = (port: number, resultsDir: string) => ({
  command: 'node ./dist/server/entry.mjs',
  url: `http://127.0.0.1:${port}/`,
  reuseExistingServer: false,
  timeout: 60_000,
  env: { RESULTS_DIR: resultsDir, HOST: '127.0.0.1', PORT: String(port) },
});

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [['list']],
  webServer: [server(POPULATED_PORT, dirs.populated), server(EMPTY_PORT, dirs.empty)],
  projects: [
    {
      name: 'populated',
      testIgnore: /empty\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], baseURL: `http://127.0.0.1:${POPULATED_PORT}` },
    },
    {
      name: 'empty',
      testMatch: /empty\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], baseURL: `http://127.0.0.1:${EMPTY_PORT}` },
    },
  ],
});
