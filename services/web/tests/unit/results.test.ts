import { afterAll, describe, expect, it } from 'vitest';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { isValidFlightId, listFlights, readFlight } from '../../src/lib/results.ts';

const root = mkdtempSync(join(tmpdir(), 'ardu-web-unit-'));

function dir(name: string): string {
  const path = join(root, name);
  mkdirSync(path, { recursive: true });
  return path;
}

const FLIGHT = {
  flight_id: 'flight-01',
  duration_s: 120,
  phases: [],
  metrics: { reaction_latency_ms: 200 },
  default_thresholds: { reaction_latency_ms: { good_max: 500, warn_max: 1000 } },
  series: { t: [0, 1], roll: [0, 0], pitch: [0, 0], att_roll: [0, 0], att_pitch: [0, 0] },
  amplitude_histogram: { roll: { bins: [], counts: [] }, pitch: { bins: [], counts: [] }, yaw: { bins: [], counts: [] } },
};

const EMPTY_DIR = dir('empty');

const ONE_DIR = dir('one');
writeFileSync(join(ONE_DIR, 'flight-01.json'), JSON.stringify(FLIGHT));
writeFileSync(join(ONE_DIR, 'flight-02.json.tmp'), '{"flight_id":');

const ERROR_DIR = dir('with-error');
writeFileSync(
  join(ERROR_DIR, 'flight-bad.error.json'),
  JSON.stringify({ flight_id: 'flight-bad', error: 'DFReader crashed' }),
);

afterAll(() => rmSync(root, { recursive: true, force: true }));

describe('isValidFlightId', () => {
  it.each([['flight-01'], ['a_B-9'], ['FLIGHT2026']])('приймає валідний id %s', (id) => {
    // Arrange
    const candidate = id;

    // Act
    const valid = isValidFlightId(candidate);

    // Assert
    expect(valid).toBe(true);
  });

  it.each([['../etc/passwd'], ['a/b'], ['a.b'], [''], ['..'], ['flight 01']])(
    'відхиляє небезпечний або невалідний id %s',
    (id) => {
      // Arrange
      const candidate = id;

      // Act
      const valid = isValidFlightId(candidate);

      // Assert
      expect(valid).toBe(false);
    },
  );
});

describe('listFlights', () => {
  it('на порожній теці результатів повертає порожній список', async () => {
    // Arrange
    const results = EMPTY_DIR;

    // Act
    const flights = await listFlights(results);

    // Assert
    expect(flights).toEqual([]);
  });

  it('на неіснуючій теці повертає порожній список замість винятку', async () => {
    // Arrange
    const results = join(root, 'no-such-dir');

    // Act
    const flights = await listFlights(results);

    // Assert
    expect(flights).toEqual([]);
  });

  it('ігнорує проміжні файли атомарного запису (.json.tmp)', async () => {
    // Arrange
    const results = ONE_DIR;

    // Act
    const flights = await listFlights(results);

    // Assert
    expect(flights.map((f) => f.flight_id)).toEqual(['flight-01']);
  });

  it('не тягне важкі series у шапку списку', async () => {
    // Arrange
    const results = ONE_DIR;

    // Act
    const flights = await listFlights(results);

    // Assert
    expect(flights[0]).not.toHaveProperty('series');
  });

  it('позначає .error.json-політ статусом error', async () => {
    // Arrange
    const results = ERROR_DIR;

    // Act
    const flights = await listFlights(results);

    // Assert
    expect(flights[0].status).toBe('error');
  });
});

describe('readFlight', () => {
  it('повертає розібраний політ для існуючого id', async () => {
    // Arrange
    const results = ONE_DIR;

    // Act
    const payload = await readFlight('flight-01', results);

    // Assert
    expect(payload).toEqual({ status: 'ok', flight: FLIGHT });
  });

  it('повертає null для неіснуючого політу', async () => {
    // Arrange
    const results = ONE_DIR;

    // Act
    const payload = await readFlight('flight-zzz', results);

    // Assert
    expect(payload).toBeNull();
  });

  it('повертає null для невалідного id без звернення до ФС', async () => {
    // Arrange
    const results = ONE_DIR;

    // Act
    const payload = await readFlight('../results', results);

    // Assert
    expect(payload).toBeNull();
  });

  it('повертає статус error для політу з .error.json', async () => {
    // Arrange
    const results = ERROR_DIR;

    // Act
    const payload = await readFlight('flight-bad', results);

    // Assert
    expect(payload).toEqual({
      status: 'error',
      error: { flight_id: 'flight-bad', error: 'DFReader crashed' },
    });
  });
});
