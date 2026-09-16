/**
 * JSON-джерело для клієнтського поллінгу списку польотів (замінює htmx-партіал).
 * `readdir` — усередині обробника, сканується на кожен запит (SSR-контракт).
 */
import type { APIRoute } from 'astro';
import { listFlights } from '../../lib/results.ts';

export const prerender = false;

export const GET: APIRoute = async () => {
  const flights = await listFlights();
  return new Response(JSON.stringify(flights), {
    headers: { 'Content-Type': 'application/json' },
  });
};
