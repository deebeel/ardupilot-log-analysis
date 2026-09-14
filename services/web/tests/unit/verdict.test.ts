import { describe, expect, it } from 'vitest';
import {
  categorize,
  computeVerdict,
  correctionsCount,
  formatMetricValue,
  withCrashOverride,
} from '../../src/lib/verdict.ts';
import type { AxisValues, Metrics, Thresholds } from '../../src/lib/types.ts';

const T = { good_max: 6, warn_max: 12 };

const FULL_THRESHOLDS: Thresholds = {
  corrections_per_min: { good_max: 6, warn_max: 12 },
  mean_amplitude: { good_max: 0.15, warn_max: 0.3 },
  mean_jerk: { good_max: 0.6, warn_max: 1.2 },
  oscillation_time_pct: { good_max: 0.1, warn_max: 0.25 },
  reaction_latency_ms: { good_max: 500, warn_max: 1000 },
};

const GOOD_METRICS: Metrics = {
  corrections_per_min: { roll: 2, pitch: 1.5, yaw: 0.3 },
  mean_amplitude: { roll: 0.05, pitch: 0.04, yaw: 0.01 },
  mean_jerk: { roll: 0.2, pitch: 0.15, yaw: 0.02 },
  oscillation_time_pct: { roll: 0.02, pitch: 0.01, yaw: 0 },
  reaction_latency_ms: 200,
};

function withJerkRoll(value: number): Metrics {
  return { ...GOOD_METRICS, mean_jerk: { ...GOOD_METRICS.mean_jerk, roll: value } };
}

describe('categorize — межі порогів', () => {
  it.each([
    ['значно нижче good_max', 0, 'good'],
    ['трохи нижче good_max', 5.999, 'good'],
    ['рівно good_max (порівняння <=)', 6, 'good'],
    ['перша точка за good_max', 6.001, 'warning'],
    ['трохи нижче warn_max', 11.999, 'warning'],
    ['рівно warn_max (ще warning, не bad)', 12, 'warning'],
    ['перша точка за warn_max', 12.001, 'bad'],
    ['значно вище warn_max', 1000, 'bad'],
    ['від’ємне значення', -5, 'good'],
  ])('значення %s → %s', (_name, value, expected) => {
    // Arrange
    const threshold = T;

    // Act
    const category = categorize(value, threshold);

    // Assert
    expect(category).toBe(expected);
  });

  it.each([
    ['NaN', Number.NaN, 'unknown'],
    ['null', null, 'unknown'],
    ['undefined', undefined, 'unknown'],
    ['рядок', '7', 'unknown'],
    ['+Infinity', Number.POSITIVE_INFINITY, 'bad'],
    ['-Infinity', Number.NEGATIVE_INFINITY, 'good'],
  ])('нечислове/нескінченне значення %s → %s', (_name, value, expected) => {
    // Arrange
    const threshold = T;

    // Act
    const category = categorize(value, threshold);

    // Assert
    expect(category).toBe(expected);
  });

  it('зіпсований конфіг (warn_max < good_max) не кидає винятку', () => {
    // Arrange
    const broken = { good_max: 12, warn_max: 6 };

    // Act
    const category = categorize(8, broken);

    // Assert
    expect(category).toBe('good');
  });
});

describe('computeVerdict — worst-case агрегація', () => {
  it('усі метрики в межах порогів дають вердикт good', () => {
    // Arrange
    const metrics = GOOD_METRICS;

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.verdict).toBe('good');
  });

  it('одна вісь у warning серед хороших не розчиняється у загальному вердикті', () => {
    // Arrange
    const metrics = withJerkRoll(0.9);

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.verdict).toBe('warning');
  });

  it('одна вісь у bad серед хороших робить весь політ bad', () => {
    // Arrange
    const metrics = withJerkRoll(1.6);

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.verdict).toBe('bad');
  });

  it('за одночасних warning і bad перемагає bad', () => {
    // Arrange
    const metrics: Metrics = {
      ...GOOD_METRICS,
      mean_jerk: { roll: 1.6, pitch: 0.9, yaw: 0.02 },
    };

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.verdict).toBe('bad');
  });

  it('порядок ключів у наборі метрик не впливає на вердикт', () => {
    // Arrange
    const reordered = {
      reaction_latency_ms: GOOD_METRICS.reaction_latency_ms,
      mean_jerk: { roll: 1.6, pitch: 0.15, yaw: 0.02 },
      oscillation_time_pct: GOOD_METRICS.oscillation_time_pct,
      mean_amplitude: GOOD_METRICS.mean_amplitude,
      corrections_per_min: GOOD_METRICS.corrections_per_min,
    };

    // Act
    const result = computeVerdict(reordered, FULL_THRESHOLDS);

    // Assert
    expect(result.verdict).toBe('bad');
  });

  it('NaN у метриці не псує загальний вердикт хорошого польоту', () => {
    // Arrange
    const metrics = withJerkRoll(Number.NaN);

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.verdict).toBe('good');
  });

  it('Infinity у метриці дає загальний вердикт bad', () => {
    // Arrange
    const metrics = withJerkRoll(Number.POSITIVE_INFINITY);

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.verdict).toBe('bad');
  });
});

describe('computeVerdict — reasons', () => {
  it('хороший політ не дає жодної причини категорії bad', () => {
    // Arrange
    const metrics = GOOD_METRICS;

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.reasons.filter((r) => r.category === 'bad')).toEqual([]);
  });

  it('порушення адресується саме тій метриці й осі, що вийшла за поріг', () => {
    // Arrange
    const metrics = withJerkRoll(1.6);

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.reasons).toContainEqual({
      metric: 'mean_jerk',
      axis: 'roll',
      value: 1.6,
      category: 'bad',
    });
  });

  it('скалярна метрика reaction_latency_ms потрапляє в reasons без осі', () => {
    // Arrange
    const metrics = GOOD_METRICS;

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.reasons).toContainEqual({
      metric: 'reaction_latency_ms',
      axis: null,
      value: 200,
      category: 'good',
    });
  });

  it('повний набір дає рівно 13 причин (4 метрики × 3 осі + 1 скаляр)', () => {
    // Arrange
    const metrics = GOOD_METRICS;

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.reasons).toHaveLength(13);
  });
});

describe('computeVerdict — деградація вхідних даних', () => {
  it('метрика без порога ігнорується і не робить політ поганим', () => {
    // Arrange
    const thresholds: Thresholds = { mean_amplitude: FULL_THRESHOLDS.mean_amplitude };

    // Act
    const result = computeVerdict(withJerkRoll(99), thresholds);

    // Assert
    expect(result.verdict).toBe('good');
  });

  it('поріг без відповідної метрики не потрапляє у reasons', () => {
    // Arrange
    const metrics = { mean_amplitude: GOOD_METRICS.mean_amplitude };

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.reasons.map((r) => r.metric)).toEqual([
      'mean_amplitude',
      'mean_amplitude',
      'mean_amplitude',
    ]);
  });

  it('null як значення осі дає категорію unknown без винятку', () => {
    // Arrange
    const metrics = { mean_jerk: { roll: null, pitch: 0.1, yaw: 0.02 } };

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.reasons[0].category).toBe('unknown');
  });

  it('порожній набір метрик дає вердикт good', () => {
    // Arrange
    const metrics = {};

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.verdict).toBe('good');
  });

  it('порожній набір метрик дає порожній reasons', () => {
    // Arrange
    const metrics = {};

    // Act
    const result = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(result.reasons).toEqual([]);
  });

  it('порожній конфіг порогів дає порожній reasons', () => {
    // Arrange
    const thresholds = {};

    // Act
    const result = computeVerdict(GOOD_METRICS, thresholds);

    // Assert
    expect(result.reasons).toEqual([]);
  });
});

describe('computeVerdict — чистота функції', () => {
  it('виклик не мутує переданий набір метрик', () => {
    // Arrange
    const metrics = structuredClone(GOOD_METRICS);
    const snapshot = structuredClone(GOOD_METRICS);

    // Act
    computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(metrics).toEqual(snapshot);
  });

  it('два виклики з тими самими аргументами дають однаковий результат', () => {
    // Arrange
    const metrics = withJerkRoll(1.6);

    // Act
    const first = computeVerdict(metrics, FULL_THRESHOLDS);

    // Assert
    expect(first).toEqual(computeVerdict(metrics, FULL_THRESHOLDS));
  });
});

describe('correctionsCount — дискретна кількість корекцій', () => {
  it.each([
    ['типовий випадок', { roll: 4.1796, pitch: 3.7152, yaw: 0 }, 109.2, { roll: 8, pitch: 7, yaw: 0 }],
    ['точно ціла кількість без округлення', { roll: 6, pitch: 0, yaw: 0 }, 60, { roll: 6, pitch: 0, yaw: 0 }],
    ['нульова швидкість на всіх осях', { roll: 0, pitch: 0, yaw: 0 }, 90, { roll: 0, pitch: 0, yaw: 0 }],
  ] as [string, AxisValues, number, AxisValues][])(
    '%s',
    (_label, correctionsPerMin, analyzedDurationS, expected) => {
      // Arrange / Act
      const result = correctionsCount(correctionsPerMin, analyzedDurationS);

      // Assert
      expect(result).toEqual(expected);
    },
  );

  it.each([0, -5])('analyzedDurationS <= 0 (%s) дає нулі на всіх осях', (analyzedDurationS) => {
    // Arrange
    const correctionsPerMin: AxisValues = { roll: 4, pitch: 3, yaw: 2 };

    // Act
    const result = correctionsCount(correctionsPerMin, analyzedDurationS);

    // Assert
    expect(result).toEqual({ roll: 0, pitch: 0, yaw: 0 });
  });
});

describe('withCrashOverride — фізичний інцидент переважає числові пороги', () => {
  it.each([
    ['good', true, 'crashed'],
    ['warning', true, 'crashed'],
    ['bad', true, 'crashed'],
    ['good', false, 'good'],
    ['bad', false, 'bad'],
  ] as const)('verdict=%s, crashed=%s -> %s', (verdict, crashed, expected) => {
    // Arrange / Act
    const result = withCrashOverride(verdict, crashed);

    // Assert
    expect(result).toBe(expected);
  });
});

describe('formatMetricValue — дискретні метрики без хвоста десяткових', () => {
  it.each([
    ['corrections_per_min', 4.1796, '4'],
    ['corrections_per_min', 4.5, '5'],
    ['reaction_latency_ms', 700.3, '700'],
  ])('%s(%s) -> %s', (metric, value, expected) => {
    // Arrange / Act
    const result = formatMetricValue(metric, value);

    // Assert
    expect(result).toBe(expected);
  });

  it.each([
    ['mean_amplitude', 0.8535],
    ['mean_jerk', 0.0944],
    ['oscillation_time_pct', 0.0],
  ])('%s лишається неперервним, без округлення', (metric, value) => {
    // Arrange / Act
    const result = formatMetricValue(metric, value);

    // Assert
    expect(result).toBe(String(value));
  });
});
