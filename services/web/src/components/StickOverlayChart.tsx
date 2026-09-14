/** Графік положення стіків (RCIN) поверх attitude (ATT) у часі. uPlot, у бандлі, без CDN. */
import { useEffect, useRef } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import type { Series } from '../lib/types.ts';
import { attachWheelZoom, resetXScale, type AxisBounds } from '../lib/chartZoom.ts';

interface Props {
  series: Series;
}

export default function StickOverlayChart({ series }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<uPlot | null>(null);
  const boundsRef = useRef<AxisBounds>({ min: 0, max: 1 });

  useEffect(() => {
    const el = host.current;
    if (el === null) {
      return;
    }
    const data: uPlot.AlignedData = [
      series.t,
      series.roll,
      series.pitch,
      series.att_roll,
      series.att_pitch,
    ];
    boundsRef.current = { min: series.t[0] ?? 0, max: series.t[series.t.length - 1] ?? 1 };
    const chart = new uPlot(
      {
        width: el.clientWidth || 800,
        height: 320,
        cursor: { drag: { x: true, y: false } },
        scales: { x: { time: false } },
        axes: [
          { stroke: '#94a3b8', grid: { stroke: '#1e293b' }, label: 'час, с' },
          { stroke: '#94a3b8', grid: { stroke: '#1e293b' }, label: 'норм. відхилення' },
        ],
        series: [
          { label: 't' },
          { label: 'stick roll', stroke: '#38bdf8', width: 1.5 },
          { label: 'stick pitch', stroke: '#a78bfa', width: 1.5 },
          { label: 'att roll', stroke: '#fbbf24', width: 1, dash: [6, 4] },
          { label: 'att pitch', stroke: '#f87171', width: 1, dash: [6, 4] },
        ],
      },
      data,
      el,
    );
    chartRef.current = chart;

    const detachWheelZoom = attachWheelZoom(chart, boundsRef.current);
    const resize = () => chart.setSize({ width: el.clientWidth || 800, height: 320 });
    const observer = new ResizeObserver(resize);
    observer.observe(el);

    return () => {
      detachWheelZoom();
      observer.disconnect();
      chart.destroy();
      chartRef.current = null;
    };
  }, [series]);

  const resetView = (): void => {
    if (chartRef.current !== null) {
      resetXScale(chartRef.current, boundsRef.current);
    }
  };

  return (
    <div>
      <button
        type="button"
        data-testid="chart-reset-view"
        onClick={resetView}
        className="mb-2 rounded border border-slate-700 px-2 py-1 text-xs text-slate-400 hover:bg-slate-800"
      >
        Скинути масштаб
      </button>
      <div ref={host} data-testid="stick-chart" className="w-full" />
    </div>
  );
}
