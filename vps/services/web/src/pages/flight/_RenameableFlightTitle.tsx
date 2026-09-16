/**
 * Заголовок сторінки деталей із перейменуванням — той самий `localStorage`-підхід,
 * що й у `FlightList`, лише для одного flight_id, без поллінгу. `getStoredName`
 * синхронна, тож береться прямо під час рендеру; `renameTick` лише примушує
 * перерендер після запису (React сам не бачить зміни в `localStorage`).
 */
import { useState } from 'react';
import { getStoredName, setStoredName } from '../../lib/localName.ts';

interface Props {
  flightId: string;
}

export default function RenameableFlightTitle({ flightId }: Props) {
  const [, forceRerender] = useState(0);

  const rename = (): void => {
    const next = window.prompt('Назва польоту:', getStoredName(flightId) ?? flightId);
    if (next === null) {
      return;
    }
    setStoredName(flightId, next.trim());
    forceRerender((tick) => tick + 1);
  };

  return (
    <h1 className="mb-1 flex items-center gap-2 font-mono text-2xl font-semibold" data-testid="flight-title">
      <span data-testid="flight-name">{getStoredName(flightId) ?? flightId}</span>
      <button
        type="button"
        data-testid="rename-flight"
        aria-label="Перейменувати політ"
        onClick={rename}
        className="rounded border border-slate-700 px-2 py-0.5 text-sm text-slate-400 hover:bg-slate-800"
      >
        ✎
      </button>
    </h1>
  );
}
