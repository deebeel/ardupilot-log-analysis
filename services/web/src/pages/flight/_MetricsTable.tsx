/**
 * Одна таблиця метрик для ОДНІЄЇ осі (roll/pitch/yaw) — приватний хелпер
 * `VerdictPanel`, використовується 3 рази (по осі), тому виправдано як
 * окремий файл, а не інлайн-JSX. Назва з `_` — сигнал "не для імпорту
 * ззовні цього каталогу", той самий підхід, що й `_FlightError`/`_FlightSuccess`
 * у `pages/flight/`.
 */
import { CELL_TEXT_CLASSES, formatMetricValue, type Reason } from '../../lib/verdict.ts';

interface Props {
  axis: string;
  /** Уже відфільтровані `reasons` для цієї осі (без скалярних, напр. reaction_latency_ms). */
  reasons: Reason[];
  /** Дискретна кількість корекцій саме для цієї осі — показується лише в рядку corrections_per_min. */
  correctionsCount: number;
}

export default function MetricsTable({ axis, reasons, correctionsCount }: Props) {
  return (
    <div>
      <div className="mb-2 font-mono text-xs uppercase text-slate-400">{axis}</div>
      <table className="w-full text-left text-sm" data-testid={`metrics-table-${axis}`}>
        <thead className="text-xs uppercase text-slate-500">
          <tr>
            <th className="py-1">метрика</th>
            <th className="py-1">значення</th>
            <th className="py-1">кількість</th>
            <th className="py-1">категорія</th>
          </tr>
        </thead>
        <tbody>
          {reasons.map((reason) => (
            <tr key={reason.metric} className="border-t border-slate-800">
              <td className="py-1 font-mono text-xs">{reason.metric}</td>
              <td className="py-1 tabular-nums">{formatMetricValue(reason.metric, reason.value)}</td>
              <td className="py-1 tabular-nums" data-testid={`count-${reason.metric}-${axis}`}>
                {reason.metric === 'corrections_per_min' ? correctionsCount : '—'}
              </td>
              <td className={`py-1 font-medium ${CELL_TEXT_CLASSES[reason.category]}`}>{reason.category}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
