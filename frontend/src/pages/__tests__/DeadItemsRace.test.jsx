/**
 * Dead Items frontend audit fixtures — real component, mocked axios.
 *  - Two As-of requests resolving in reverse order: later request must win.
 *  - Date input always syncs to the backend's effective as_of.
 *  - Column sorting applies to the provisional table too.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import axios from 'axios';
import DeadItems from '../DeadItems';

jest.mock('axios');
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

global.IS_REACT_ACT_ENVIRONMENT = true;

const mkRow = (name, over = {}) => ({
  item_name: name, stamp: 'X', merged_names: [], stock_net_kg: 10,
  first_purchase: '2026-01-01', observed_days: 100, total_net_sales_kg: 1,
  avg_monthly_sale_kg: 0.3, months_to_clear: 33.3, last_sale_date: '2026-02-01',
  sales_90d_kg: 0, status: 'ok', provisional: false, review_reasons: [], ...over,
});

const mkData = (asOf, items) => ({
  items, review: [], removed: [],
  summary: { threshold: 3, confirmed_dead: 0, provisional_dead: 0, no_net_sales: 0, needs_review: 0, dead_total: 0 },
  as_of: asOf, last_txn_date: '2026-07-15', history_start: '2023-01-01',
  method: 'First recorded purchase / zero-opening estimate',
  coverage: { cutoff: '2026-07-15', verified: false, source: 'last_transaction_fallback', explicit_as_of: false },
});

const deferred = () => {
  let resolve, reject;
  const p = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { p, resolve, reject };
};

const setNativeValue = (el, value) => {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(el, value);
  el.dispatchEvent(new Event('input', { bubbles: true }));
};

let container, root;
beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => { root.unmount(); });
  container.remove();
  jest.resetAllMocks();
});

test('stale earlier As-of response cannot overwrite a later request', async () => {
  const calls = [];
  axios.get.mockImplementation((url) => {
    const d = deferred();
    calls.push({ url, d });
    return d.p;
  });

  await act(async () => { root.render(<DeadItems />); });
  expect(calls).toHaveLength(1); // initial default-as-of request (A)

  const input = container.querySelector('[data-testid="as-of-input"]');
  await act(async () => { setNativeValue(input, '2026-01-15'); });
  await act(async () => { input.dispatchEvent(new FocusEvent('focusout', { bubbles: true })); });
  expect(calls).toHaveLength(2);
  expect(calls[1].url).toContain('as_of=2026-01-15'); // request B

  // B (newer) resolves FIRST, then slow A arrives late
  await act(async () => { calls[1].d.resolve({ data: mkData('2026-01-15', [mkRow('B-ITEM')]) }); });
  await act(async () => { calls[0].d.resolve({ data: mkData('2026-07-10', [mkRow('A-ITEM')]) }); });

  expect(input.value).toBe('2026-01-15'); // stale A must not overwrite date
  expect(container.querySelector('[data-testid="dead-row-B-ITEM"]')).not.toBeNull();
  expect(container.querySelector('[data-testid="dead-row-A-ITEM"]')).toBeNull();
});

test('date input syncs to the backend effective as_of', async () => {
  axios.get.mockResolvedValue({ data: mkData('2026-07-15', [mkRow('ONLY')]) });
  await act(async () => { root.render(<DeadItems />); });
  const input = container.querySelector('[data-testid="as-of-input"]');
  expect(input.value).toBe('2026-07-15');
  expect(container.querySelector('[data-testid="coverage-note"]').textContent)
    .toContain('Unverified');
});

test('column sorting applies to the provisional table', async () => {
  axios.get.mockResolvedValue({
    data: mkData('2026-07-15', [
      mkRow('ZZ', { months_to_clear: 50 }),
      mkRow('AA', { months_to_clear: 40 }),
      mkRow('P-ZZ', { provisional: true, observed_days: 10, months_to_clear: 30 }),
      mkRow('P-AA', { provisional: true, observed_days: 12, months_to_clear: 20 }),
    ]),
  });
  await act(async () => { root.render(<DeadItems />); });

  const provNames = () => [...container
    .querySelector('[data-testid="provisional-table"]')
    .querySelectorAll('tbody tr')].map((tr) => tr.getAttribute('data-testid'));

  expect(provNames()).toEqual(['dead-row-P-ZZ', 'dead-row-P-AA']); // default: score desc

  const th = container.querySelector('[data-testid="sort-item_name"]');
  await act(async () => { th.click(); }); // desc by name
  await act(async () => { th.click(); }); // asc by name
  expect(provNames()).toEqual(['dead-row-P-AA', 'dead-row-P-ZZ']);

  const deadNames = () => [...container
    .querySelector('[data-testid="dead-items-table"]')
    .querySelectorAll('tbody tr')].map((tr) => tr.getAttribute('data-testid'));
  expect(deadNames()).toEqual(['dead-row-AA', 'dead-row-ZZ']);
});
