/** Контракт JSON польоту, який пише сервіс `parser` у RESULTS_DIR. */

export type Axis = 'roll' | 'pitch' | 'yaw';

/** Значення метрики з розбивкою по осях. */
export interface AxisValues {
  roll: number;
  pitch: number;
  yaw: number;
}

/** Сирі детерміновані метрики (шар 1 — див. docs/scoring-algorithm.md). */
export interface Metrics {
  corrections_per_min: AxisValues;
  mean_amplitude: AxisValues;
  mean_jerk: AxisValues;
  oscillation_time_pct: AxisValues;
  reaction_latency_ms: number;
}

export interface Threshold {
  good_max: number;
  warn_max: number;
}

/** Дефолтні пороги з thresholds.yaml — стартові значення форми в UI. */
export type Thresholds = Partial<Record<keyof Metrics, Threshold>>;

export interface Phase {
  mode: string;
  start_s: number;
  duration_s: number;
}

export interface Series {
  t: number[];
  roll: number[];
  pitch: number[];
  att_roll: number[];
  att_pitch: number[];
}

export interface Histogram {
  bins: number[];
  counts: number[];
}

export type AmplitudeHistogram = Record<Axis, Histogram>;

export interface Flight {
  flight_id: string;
  duration_s: number;
  /** Тривалість проаналізованих (ручних) фаз, с — база для `corrections_per_min`. */
  analyzed_duration_s: number;
  phases: Phase[];
  metrics: Metrics;
  default_thresholds: Thresholds;
  series: Series;
  amplitude_histogram: AmplitudeHistogram;
  /** `STAT.Crash` (ArduPilot, AUTO-only) АБО евристика парсера по хвосту логу. */
  crashed: boolean;
}

/** Політ, парсинг якого впав: `<flight_id>.error.json`. */
export interface FlightError {
  flight_id: string;
  error: string;
}

/** Шапка для індексної сторінки — без важких `series`. */
export interface FlightSummary {
  flight_id: string;
  status: 'ok' | 'error';
  duration_s: number | null;
  error: string | null;
  metrics: Metrics | null;
  default_thresholds: Thresholds | null;
  crashed: boolean;
}
