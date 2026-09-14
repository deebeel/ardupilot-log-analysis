/**
 * React-острів (`client:load`): слайдери порогів → миттєвий перерахунок вердикту
 * у браузері, без запиту на сервер. Сервер віддає лише метрики + дефолтні пороги.
 */
import { useMemo, useState } from 'react';
import type { Metrics, Threshold, Thresholds } from '../lib/types.ts';
import {
  BADGE_CLASSES,
  computeVerdict,
  correctionsCount,
  formatMetricValue,
  verdictSummary,
  withCrashOverride,
} from '../lib/verdict.ts';

interface Props {
  metrics: Metrics;
  defaultThresholds: Thresholds;
  /** Тривалість проаналізованих (ручних) фаз, с — для дискретної кількості корекцій. */
  analyzedDurationS: number;
  /** `STAT.Crash` АБО наша евристика (парсер) — переважає над числовими порогами. */
  crashed: boolean;
}

const CELL: Record<string, string> = {
  good: 'text-emerald-300',
  warning: 'text-amber-300',
  bad: 'text-rose-300',
  crashed: 'text-red-400',
  unknown: 'text-slate-400',
};

function sliderMax(base: number): number {
  // Округлення обов'язкове: base*3 на float дає 3.5999999999999996,
  // і слайдер перестає приймати рівно 3.6.
  return Math.round(Math.max(base * 3, 1) * 1000) / 1000;
}

function round(value: number): number {
  return Math.round(value * 1000) / 1000;
}

export default function VerdictPanel({ metrics, defaultThresholds, analyzedDurationS, crashed }: Props) {
  const [thresholds, setThresholds] = useState<Thresholds>(defaultThresholds);

  const result = useMemo(() => computeVerdict(metrics, thresholds), [metrics, thresholds]);
  const verdict = withCrashOverride(result.verdict, crashed);
  const names = Object.keys(defaultThresholds) as (keyof Thresholds)[];
  const counts = useMemo(
    () => correctionsCount(metrics.corrections_per_min, analyzedDurationS),
    [metrics.corrections_per_min, analyzedDurationS],
  );

  const update = (name: keyof Thresholds, field: keyof Threshold, value: number) => {
    setThresholds((prev) => {
      const current = prev[name];
      if (current === undefined) {
        return prev;
      }
      return { ...prev, [name]: { ...current, [field]: value } };
    });
  };

  const reset = () => setThresholds(defaultThresholds);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <span
          data-testid="verdict"
          data-verdict={verdict}
          className={`rounded-md border px-3 py-1 text-sm font-semibold uppercase ${BADGE_CLASSES[verdict]}`}
        >
          {verdict}
        </span>
        <span data-testid="verdict-summary" className="text-sm text-slate-300">
          {crashed ? 'CRASHED: апарат зазнав аварії (удар/розбиття)' : verdictSummary(result)}
        </span>
        <button
          type="button"
          data-testid="reset-thresholds"
          onClick={reset}
          className="ml-auto rounded border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-800"
        >
          Скинути пороги
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {names.map((name) => {
          const threshold = thresholds[name] as Threshold;
          const base = (defaultThresholds[name] as Threshold).warn_max;
          return (
            <div key={String(name)} className="rounded-lg border border-slate-800 bg-slate-900/50 p-3">
              <div className="mb-2 font-mono text-xs text-slate-300">{String(name)}</div>
              <label className="block text-xs text-slate-400">
                good_max: <span data-testid={`val-${String(name)}-good_max`}>{round(threshold.good_max)}</span>
                <input
                  type="range"
                  data-testid={`th-${String(name)}-good_max`}
                  min={0}
                  max={sliderMax(base)}
                  step="any"
                  value={threshold.good_max}
                  onChange={(e) => update(name, 'good_max', Number(e.target.value))}
                  className="mt-1 w-full accent-emerald-400"
                />
              </label>
              <label className="mt-2 block text-xs text-slate-400">
                warn_max: <span data-testid={`val-${String(name)}-warn_max`}>{round(threshold.warn_max)}</span>
                <input
                  type="range"
                  data-testid={`th-${String(name)}-warn_max`}
                  min={0}
                  max={sliderMax(base)}
                  step="any"
                  value={threshold.warn_max}
                  onChange={(e) => update(name, 'warn_max', Number(e.target.value))}
                  className="mt-1 w-full accent-amber-400"
                />
              </label>
            </div>
          );
        })}
      </div>

      <table className="w-full text-left text-sm" data-testid="reasons-table">
        <thead className="text-xs uppercase text-slate-500">
          <tr>
            <th className="py-1">метрика</th>
            <th className="py-1">вісь</th>
            <th className="py-1">значення</th>
            <th className="py-1">кількість</th>
            <th className="py-1">категорія</th>
          </tr>
        </thead>
        <tbody>
          {result.reasons.map((reason) => (
            <tr key={`${reason.metric}-${reason.axis ?? 'scalar'}`} className="border-t border-slate-800">
              <td className="py-1 font-mono text-xs">{reason.metric}</td>
              <td className="py-1 text-slate-400">{reason.axis ?? '—'}</td>
              <td className="py-1 tabular-nums">{formatMetricValue(reason.metric, reason.value)}</td>
              <td className="py-1 tabular-nums" data-testid={`count-${reason.metric}-${reason.axis ?? 'scalar'}`}>
                {reason.metric === 'corrections_per_min' && reason.axis !== null
                  ? counts[reason.axis as keyof typeof counts]
                  : '—'}
              </td>
              <td className={`py-1 font-medium ${CELL[reason.category]}`}>{reason.category}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
