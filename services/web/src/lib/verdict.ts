/**
 * Порт §Алгоритм з `docs/scoring-algorithm.md` на TypeScript.
 *
 * Чиста функція: `(metrics, thresholds) => {verdict, reasons}`.
 * Виконується В БРАУЗЕРІ — пороги налаштовуються слайдерами, перерахунок миттєвий.
 * Жодного LLM, лише if/else за порогами.
 */

import type { AxisValues, Metrics, Thresholds, Threshold } from './types.ts';

export type Category = 'good' | 'warning' | 'bad' | 'unknown';

export interface Reason {
  metric: string;
  /** `null` для скалярних метрик без розбивки по осях (reaction_latency_ms). */
  axis: string | null;
  value: number;
  category: Category;
}

export interface VerdictResult {
  verdict: Category;
  reasons: Reason[];
}

/** Метрики з розбивкою по осях; решта — скаляри. */
export const AXES = ['roll', 'pitch', 'yaw'] as const;

/** Чим більше число — тим гірша категорія (для worst-case агрегації). */
const SEVERITY: Record<Category, number> = {
  unknown: -1,
  good: 0,
  warning: 1,
  bad: 2,
};

/**
 * Крок 1 алгоритму: категоризація одного значення.
 * `value <= good_max` → good; `<= warn_max` → warning; інакше bad.
 * Нечислове/NaN → unknown (не впливає на загальний вердикт).
 */
export function categorize(value: unknown, threshold: Threshold): Category {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 'unknown';
  }
  if (value <= threshold.good_max) {
    return 'good';
  }
  if (value <= threshold.warn_max) {
    return 'warning';
  }
  return 'bad';
}

function isThreshold(t: unknown): t is Threshold {
  return (
    typeof t === 'object' &&
    t !== null &&
    typeof (t as Threshold).good_max === 'number' &&
    typeof (t as Threshold).warn_max === 'number'
  );
}

/** Значення метрики: або скаляр, або об'єкт {roll, pitch, yaw}. */
function reasonsForMetric(name: string, raw: unknown, threshold: Threshold): Reason[] {
  if (typeof raw === 'object' && raw !== null) {
    const byAxis = raw as Record<string, unknown>;
    return AXES.filter((axis) => axis in byAxis).map((axis) => ({
      metric: name,
      axis,
      value: byAxis[axis] as number,
      category: categorize(byAxis[axis], threshold),
    }));
  }
  return [
    {
      metric: name,
      axis: null,
      value: raw as number,
      category: categorize(raw, threshold),
    },
  ];
}

/**
 * Крок 2: загальний вердикт = НАЙГІРША категорія серед усіх метрик і осей
 * (worst-case, не середнє) — одна погана метрика не «розчиняється» у хороших.
 *
 * Метрика, для якої немає порога (або порогу немає метрики), просто ігнорується.
 * Порожній набір метрик/порогів → `good` з порожнім `reasons`.
 */
export function computeVerdict(
  metrics: Partial<Metrics> | Record<string, unknown>,
  thresholds: Thresholds | Record<string, unknown>,
): VerdictResult {
  const source = metrics as Record<string, unknown>;
  const config = thresholds as Record<string, unknown>;

  const reasons = Object.keys(config)
    .filter((name) => name in source && source[name] !== undefined && source[name] !== null)
    .filter((name) => isThreshold(config[name]))
    .flatMap((name) => reasonsForMetric(name, source[name], config[name] as Threshold));

  const worst = reasons.reduce<Category>(
    (acc, reason) => (SEVERITY[reason.category] > SEVERITY[acc] ? reason.category : acc),
    'good',
  );

  return { verdict: worst, reasons };
}

/**
 * Дискретна кількість корекцій за проаналізований (ручний) відрізок польоту.
 *
 * Парсер повертає лише похідну швидкість `corrections_per_min` — сирий
 * лічильник переходів через deadband у вихідний JSON не потрапляє. Але це
 * зворотне обчислення точне (не оцінка): `corrections_per_min` саме дорівнює
 * `count / (analyzed_duration_s / 60)`, тож множення відновлює цілий count.
 */
export function correctionsCount(
  correctionsPerMin: AxisValues,
  analyzedDurationS: number,
): AxisValues {
  if (analyzedDurationS <= 0) {
    return { roll: 0, pitch: 0, yaw: 0 };
  }
  const factor = analyzedDurationS / 60;
  return {
    roll: Math.round(correctionsPerMin.roll * factor),
    pitch: Math.round(correctionsPerMin.pitch * factor),
    yaw: Math.round(correctionsPerMin.yaw * factor),
  };
}

/** Короткий текстовий вердикт (крок 3 алгоритму) — шаблон рядка, без LLM. */
export function verdictSummary(result: VerdictResult): string {
  const offenders = result.reasons.filter((r) => r.category === result.verdict);
  const label = result.verdict.toUpperCase();
  if (result.verdict === 'good' || offenders.length === 0) {
    return `${label}: усі метрики в межах порогів`;
  }
  const listed = offenders
    .slice(0, 3)
    .map((r) => `${r.metric}${r.axis === null ? '' : `/${r.axis}`}=${r.value}`)
    .join(', ');
  return `${label}: ${listed}`;
}
