/** Гістограма амплітуд відхилень стіків по осях (uPlot, bars). */
import { useEffect, useRef } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import type { AmplitudeHistogram as HistogramData } from '../../lib/types.ts';
import { AXES } from '../../lib/verdict.ts';
import { attachWheelZoom, resetXScale, type AxisBounds } from '../../lib/chartZoom.ts';

interface Props {
  histogram: HistogramData;
}

const COLORS: Record<string, string> = {
  roll: '#38bdf8',
  pitch: '#a78bfa',
  yaw: '#34d399',
};

export default function AmplitudeHistogram({ histogram }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<uPlot | null>(null);
  const boundsRef = useRef<AxisBounds>({ min: 0, max: 1 });

  useEffect(() => {
    const el = host.current;
    if (el === null) {
      return;
    }
    const bins = histogram.roll.bins;
    const data: uPlot.AlignedData = [
      bins,
      histogram.roll.counts,
      histogram.pitch.counts,
      histogram.yaw.counts,
    ];
    boundsRef.current = { min: bins[0] ?? 0, max: bins[bins.length - 1] ?? 1 };
    const chart = new uPlot(
      {
        width: el.clientWidth || 800,
        height: 260,
        scales: { x: { time: false } },
        axes: [
          { stroke: '#94a3b8', grid: { stroke: '#1e293b' }, label: 'амплітуда' },
          { stroke: '#94a3b8', grid: { stroke: '#1e293b' }, label: 'семплів' },
        ],
        series: [
          { label: 'bin' },
          ...AXES.map((axis) => ({ label: axis, stroke: COLORS[axis], width: 2 })),
        ],
      },
      data,
      el,
    );
    chartRef.current = chart;

    const detachWheelZoom = attachWheelZoom(chart, boundsRef.current);
    const resize = () => chart.setSize({ width: el.clientWidth || 800, height: 260 });
    const observer = new ResizeObserver(resize);
    observer.observe(el);

    return () => {
      detachWheelZoom();
      observer.disconnect();
      chart.destroy();
      chartRef.current = null;
    };
  }, [histogram]);

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
      <div ref={host} data-testid="amplitude-histogram" className="w-full" />
    </div>
  );
}
