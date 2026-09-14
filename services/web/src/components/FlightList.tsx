/**
 * React-острів (`client:load`): список польотів + клієнтський поллінг раз на
 * секунду (`fetch('/api/flights')`), без htmx. Перейменування — стан
 * компонента, підхоплений з `localStorage` після монтування (щоб уникнути
 * розбіжності SSR/клієнт при першій гідратації — сервер завжди рендерить
 * `flight_id`, кастомна назва підʼїжджає одразу після mount).
 */
import { useEffect, useState } from 'react';
import type { FlightSummary } from '../lib/types.ts';
import { getStoredName, setStoredName } from '../lib/localName.ts';
import { BADGE_CLASSES, computeVerdict, withCrashOverride, type Category } from '../lib/verdict.ts';

interface Props {
  initialFlights: FlightSummary[];
}

const POLL_INTERVAL_MS = 1000;

/** Бейдж good/warning/bad/crashed — `null`, якщо metrics/пороги ще нема
 *  (лише для статусу `error`, там показуємо окремий бейдж "помилка парсингу"). */
function verdictBadge(flight: FlightSummary): Category | null {
  if (flight.metrics === null || flight.default_thresholds === null) {
    return null;
  }
  const result = computeVerdict(flight.metrics, flight.default_thresholds);
  return withCrashOverride(result.verdict, flight.crashed);
}

export default function FlightList({ initialFlights }: Props) {
  const [flights, setFlights] = useState<FlightSummary[]>(initialFlights);
  const [names, setNames] = useState<Record<string, string>>({});

  useEffect(() => {
    const loaded: Record<string, string> = {};
    for (const flight of flights) {
      const stored = getStoredName(flight.flight_id);
      if (stored) {
        loaded[flight.flight_id] = stored;
      }
    }
    setNames(loaded);
  }, []); // лише раз після mount — навмисно ігноруємо зміну `flights` як залежність

  useEffect(() => {
    const timer = window.setInterval(() => {
      fetch('/api/flights')
        .then((response) => (response.ok ? (response.json() as Promise<FlightSummary[]>) : null))
        .then((data) => {
          if (data !== null) {
            setFlights(data);
          }
        })
        .catch(() => {
          // мережева похибка одного тика — наступний спробує знову
        });
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, []);

  const rename = (flightId: string): void => {
    const next = window.prompt('Назва польоту:', names[flightId] ?? flightId);
    if (next === null) {
      return;
    }
    const trimmed = next.trim();
    setStoredName(flightId, trimmed);
    setNames((prev) => {
      const copy = { ...prev };
      if (trimmed) {
        copy[flightId] = trimmed;
      } else {
        delete copy[flightId];
      }
      return copy;
    });
  };

  if (flights.length === 0) {
    return (
      <p data-testid="empty-state" className="rounded-lg border border-slate-800 bg-slate-900/50 p-6 text-slate-400">
        Поки немає жодного розібраного польоту. Покладіть лог у watched-теку парсера — звіт з&apos;явиться тут.
      </p>
    );
  }

  return (
    <ul className="grid gap-3" data-testid="flight-list">
      {flights.map((flight) => {
        const badge = verdictBadge(flight);
        const displayName = names[flight.flight_id] ?? flight.flight_id;
        return (
          <li
            key={flight.flight_id}
            data-testid="flight-card"
            data-status={flight.status}
            className="flex items-center gap-2"
          >
            <a
              href={`/flight/${flight.flight_id}`}
              className="flex flex-1 items-center justify-between rounded-lg border border-slate-800 bg-slate-900/50 px-4 py-3 hover:border-slate-600"
            >
              <span className="font-mono" data-testid="flight-name">
                {displayName}
              </span>
              <span className="flex items-center gap-2">
                {flight.status === 'error' ? (
                  <span
                    data-testid="error-badge"
                    className="rounded border border-rose-500/40 bg-rose-500/15 px-2 py-0.5 text-xs text-rose-300"
                  >
                    помилка парсингу
                  </span>
                ) : (
                  <span className="text-sm text-slate-400">{Math.round(flight.duration_s ?? 0)} с</span>
                )}
                {badge !== null && (
                  <span
                    data-testid="verdict-badge"
                    data-verdict={badge}
                    className={`rounded-md border px-2 py-0.5 text-xs font-semibold uppercase ${BADGE_CLASSES[badge]}`}
                  >
                    {badge}
                  </span>
                )}
              </span>
            </a>
            <button
              type="button"
              data-testid="rename-flight"
              aria-label="Перейменувати політ"
              onClick={() => rename(flight.flight_id)}
              className="shrink-0 rounded border border-slate-700 px-2 py-2 text-xs text-slate-400 hover:bg-slate-800"
            >
              ✎
            </button>
          </li>
        );
      })}
    </ul>
  );
}
