/**
 * Доступ до теки результатів (RESULTS_DIR), яку пише сервіс `parser`.
 *
 * Жодного readdir на верхньому рівні модуля — модуль виконується один раз при старті
 * процесу і заморозив би список польотів. Усі функції викликаються з тіла сторінки.
 */

import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { Flight, FlightError, FlightSummary } from './types.ts';

/** Захист від path traversal: `:ro`-маунт читання чужих файлів не зупиняє. */
const ID_PATTERN = /^[A-Za-z0-9_-]+$/;

const ERROR_SUFFIX = '.error.json';
const OK_SUFFIX = '.json';

export function isValidFlightId(id: unknown): id is string {
  return typeof id === 'string' && id.length > 0 && ID_PATTERN.test(id);
}

export function resultsDir(): string {
  return process.env.RESULTS_DIR ?? '/data/results';
}

async function readJson(dir: string, file: string): Promise<unknown> {
  const raw = await readFile(join(dir, file), 'utf8');
  return JSON.parse(raw) as unknown;
}

function summaryFromFlight(flight: Flight): FlightSummary {
  // Свідомо НЕ переносимо `series`/`amplitude_histogram` — індексна сторінка
  // читає лише шапку, важкі дані в список не тягнемо.
  return {
    flight_id: flight.flight_id,
    status: 'ok',
    duration_s: flight.duration_s,
    error: null,
    metrics: flight.metrics,
    default_thresholds: flight.default_thresholds,
    crashed: flight.crashed,
  };
}

function summaryFromError(id: string, payload: FlightError): FlightSummary {
  return {
    flight_id: payload.flight_id ?? id,
    status: 'error',
    duration_s: null,
    error: payload.error ?? 'невідома помилка парсингу',
    metrics: null,
    default_thresholds: null,
    crashed: false,
  };
}

async function summarize(dir: string, file: string): Promise<FlightSummary | null> {
  const isError = file.endsWith(ERROR_SUFFIX);
  const id = file.slice(0, -(isError ? ERROR_SUFFIX.length : OK_SUFFIX.length));
  if (!isValidFlightId(id)) {
    return null;
  }
  try {
    const payload = await readJson(dir, file);
    return isError
      ? summaryFromError(id, payload as FlightError)
      : summaryFromFlight(payload as Flight);
  } catch {
    // Побитий/недописаний JSON не має валити всю сторінку списку.
    return { flight_id: id, status: 'error', duration_s: null, error: 'не вдалось прочитати JSON', metrics: null, default_thresholds: null, crashed: false };
  }
}

/** Список польотів для індексної сторінки. Сканує теку на КОЖЕН запит (SSR). */
export async function listFlights(dir = resultsDir()): Promise<FlightSummary[]> {
  let files: string[] = [];
  try {
    files = await readdir(dir);
  } catch {
    return [];
  }
  // `*.json.tmp` — проміжний файл атомарного запису парсера, ігноруємо.
  const candidates = files.filter((f) => f.endsWith(OK_SUFFIX));
  const summaries = await Promise.all(candidates.map((f) => summarize(dir, f)));
  return summaries
    .filter((s): s is FlightSummary => s !== null)
    .sort((a, b) => a.flight_id.localeCompare(b.flight_id));
}

export type FlightPayload =
  | { status: 'ok'; flight: Flight }
  | { status: 'error'; error: FlightError };

/** Читає один політ. Невалідний id або відсутній файл → `null` (сторінка віддасть 404). */
export async function readFlight(id: unknown, dir = resultsDir()): Promise<FlightPayload | null> {
  if (!isValidFlightId(id)) {
    return null;
  }
  const ok = await readJson(dir, `${id}.json`).catch(() => null);
  if (ok !== null) {
    return { status: 'ok', flight: ok as Flight };
  }
  const failed = await readJson(dir, `${id}${ERROR_SUFFIX}`).catch(() => null);
  if (failed !== null) {
    return { status: 'error', error: failed as FlightError };
  }
  return null;
}
