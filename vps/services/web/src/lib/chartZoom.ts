/**
 * Спільна логіка зуму для uPlot-графіків (StickOverlayChart, AmplitudeHistogram) —
 * використовується двічі, тому окремий модуль, а не дублювання в кожному компоненті.
 *
 * uPlot із `cursor.drag.x` дає drag-select для збільшення, але не має вбудованої
 * кнопки "скинути" чи зуму колесом — обидва додаються тут.
 */
import type uPlot from 'uplot';

export interface AxisBounds {
  min: number;
  max: number;
}

/** Скидає масштаб осі X до повного діапазону даних. */
export function resetXScale(chart: uPlot, bounds: AxisBounds): void {
  chart.setScale('x', { min: bounds.min, max: bounds.max });
}

const ZOOM_IN_FACTOR = 0.85;
const ZOOM_OUT_FACTOR = 1 / ZOOM_IN_FACTOR;
const MIN_RANGE_FRACTION = 0.01;

/**
 * Зум колесом миші навколо позиції курсора. Повертає функцію відписки.
 * `deltaY < 0` (колесо "від себе"/вгору) — наближення; інакше — віддалення.
 */
export function attachWheelZoom(chart: uPlot, bounds: AxisBounds): () => void {
  const onWheel = (event: WheelEvent): void => {
    event.preventDefault();
    const { min, max } = chart.scales.x;
    if (min == null || max == null) {
      return;
    }
    const range = max - min;
    const fullRange = bounds.max - bounds.min;
    const factor = event.deltaY < 0 ? ZOOM_IN_FACTOR : ZOOM_OUT_FACTOR;
    const newRange = Math.min(fullRange, Math.max(range * factor, fullRange * MIN_RANGE_FRACTION));

    const rect = chart.over.getBoundingClientRect();
    const cursorFraction = rect.width > 0 ? (event.clientX - rect.left) / rect.width : 0.5;
    const cursorX = min + cursorFraction * range;

    let newMin = cursorX - cursorFraction * newRange;
    let newMax = newMin + newRange;
    if (newMin < bounds.min) {
      newMin = bounds.min;
      newMax = newMin + newRange;
    }
    if (newMax > bounds.max) {
      newMax = bounds.max;
      newMin = newMax - newRange;
    }
    chart.setScale('x', { min: newMin, max: newMax });
  };

  chart.over.addEventListener('wheel', onWheel, { passive: false });
  return () => chart.over.removeEventListener('wheel', onWheel);
}
