/** Гістограма амплітуд відхилень стіків по осях (uPlot, bars). */
import { useEffect, useRef } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import type { AmplitudeHistogram as HistogramData } from '../lib/types.ts';
import { AXES } from '../lib/verdict.ts';

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

    const resize = () => chart.setSize({ width: el.clientWidth || 800, height: 260 });
    const observer = new ResizeObserver(resize);
    observer.observe(el);

    return () => {
      observer.disconnect();
      chart.destroy();
    };
  }, [histogram]);

  return <div ref={host} data-testid="amplitude-histogram" className="w-full" />;
}
