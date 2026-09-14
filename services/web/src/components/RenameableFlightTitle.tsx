/**
 * Заголовок сторінки деталей із перейменуванням — той самий `localStorage`-підхід,
 * що й у `FlightList`, лише для одного flight_id, без поллінгу.
 */
import { useEffect, useState } from 'react';
import { getStoredName, setStoredName } from '../lib/localName.ts';

interface Props {
  flightId: string;
}

export default function RenameableFlightTitle({ flightId }: Props) {
  const [name, setName] = useState(flightId);

  useEffect(() => {
    const stored = getStoredName(flightId);
    if (stored) {
      setName(stored);
    }
  }, [flightId]);

  const rename = (): void => {
    const next = window.prompt('Назва польоту:', name);
    if (next === null) {
      return;
    }
    const trimmed = next.trim();
    setStoredName(flightId, trimmed);
    setName(trimmed || flightId);
  };

  return (
    <h1 className="mb-1 flex items-center gap-2 font-mono text-2xl font-semibold" data-testid="flight-title">
      <span data-testid="flight-name">{name}</span>
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
