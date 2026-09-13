/**
 * Генератор тимчасових тек RESULTS_DIR для E2E: реальні файли на диску,
 * які читає реально піднятий SSR-сервер (ніяких моків ФС).
 */
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const POINTS = 2000;

const DEFAULT_THRESHOLDS = {
  corrections_per_min: { good_max: 6.0, warn_max: 12.0 },
  mean_amplitude: { good_max: 0.15, warn_max: 0.3 },
  mean_jerk: { good_max: 0.6, warn_max: 1.2 },
  oscillation_time_pct: { good_max: 0.1, warn_max: 0.25 },
  reaction_latency_ms: { good_max: 500, warn_max: 1000 },
};

function series(scale: number) {
  const t: number[] = [];
  const roll: number[] = [];
  const pitch: number[] = [];
  const attRoll: number[] = [];
  const attPitch: number[] = [];
  for (let i = 0; i < POINTS; i += 1) {
    const time = i * 0.1;
    t.push(time);
    roll.push(scale * Math.sin(time / 3));
    pitch.push(scale * Math.cos(time / 5));
    attRoll.push(scale * 0.8 * Math.sin(time / 3 - 0.3));
    attPitch.push(scale * 0.8 * Math.cos(time / 5 - 0.3));
  }
  return { t, roll, pitch, att_roll: attRoll, att_pitch: attPitch };
}

function histogram() {
  const bins = Array.from({ length: 20 }, (_, i) => i / 20);
  const counts = bins.map((_, i) => 200 - i * 8);
  return { roll: { bins, counts }, pitch: { bins, counts }, yaw: { bins, counts } };
}

const axis = (base: number) => ({ roll: base, pitch: base * 0.7, yaw: base * 0.2 });

/** Усі метрики впевнено під good_max. */
function goodMetrics() {
  return {
    corrections_per_min: axis(2.0),
    mean_amplitude: axis(0.05),
    mean_jerk: axis(0.2),
    oscillation_time_pct: axis(0.02),
    reaction_latency_ms: 200,
  };
}

function flight(id: string, metrics: ReturnType<typeof goodMetrics>) {
  return {
    flight_id: id,
    duration_s: 200,
    phases: [
      { mode: 'FBWA', start_s: 0, duration_s: 120 },
      { mode: 'MANUAL', start_s: 120, duration_s: 80 },
    ],
    metrics,
    default_thresholds: DEFAULT_THRESHOLDS,
    series: series(0.3),
    amplitude_histogram: histogram(),
  };
}

export interface FixtureDirs {
  populated: string;
  empty: string;
}

export function prepareFixtures(): FixtureDirs {
  const root = mkdtempSync(join(tmpdir(), 'ardu-web-e2e-'));
  const populated = join(root, 'populated');
  const empty = join(root, 'empty');
  mkdirSync(populated);
  mkdirSync(empty);

  const write = (name: string, payload: unknown) =>
    writeFileSync(join(populated, name), JSON.stringify(payload), 'utf8');

  // усі метрики під good_max
  write('flight-good.json', flight('flight-good', goodMetrics()));
  // рівно одна вісь однієї метрики за warn_max (1.6 > 1.2) → worst-case дає bad
  const bad = goodMetrics();
  bad.mean_jerk = { ...bad.mean_jerk, roll: 1.6 };
  write('flight-bad.json', flight('flight-bad', bad));
  write('flight-broken.error.json', {
    flight_id: 'flight-broken',
    error: 'DFReader: unexpected end of file at offset 12345',
  });
  // проміжний файл атомарного запису парсера — не має потрапити у список
  writeFileSync(join(populated, 'flight-partial.json.tmp'), '{"flight_id":', 'utf8');

  return { populated, empty };
}
