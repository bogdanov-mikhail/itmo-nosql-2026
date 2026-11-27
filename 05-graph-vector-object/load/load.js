import http from 'k6/http';
import { check } from 'k6';
import { Counter, Trend } from 'k6/metrics';

const serverErrors = new Counter('server_errors');
const networkErrors = new Counter('network_errors');

// Trends только для сводки по типам и глубинам: у http_req_duration
// k6 печатает подметрики лишь для групп, на которые заданы пороги.
const typeDuration = {
  lineage: new Trend('lineage_duration', true),
  path: new Trend('path_duration', true),
  search: new Trend('search_duration', true),
};
const depthDuration = {};
for (let depth = 2; depth <= 6; depth++) {
  depthDuration[depth] = new Trend(`lineage_depth_${depth}_duration`, true);
}

const BASE = (__ENV.BASE_URL || 'http://api:28080').replace(/\/+$/, '');
const SEARCH_TERMS = [
  'appointments',
  'clients',
  'mart',
  'report',
  'visits',
  'revenue',
  'gen',
  'массаж',
];

function stages() {
  switch (__ENV.MODE) {
    case 'smoke':
      return [{ duration: '1s', target: 1 }];
    case 'verify':
      return [{ duration: '5s', target: 4 }, { duration: '20s', target: 4 }];
    default:
      return [{ duration: '30s', target: 8 }, { duration: '180s', target: 8 }];
  }
}

export const options = {
  scenarios: {
    default: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: stages(),
    },
  },
  thresholds: {
    server_errors: ['count==0'],
    checks: ['rate==1'],
    'http_req_duration{type:lineage,depth:2}': ['p(95)<500'],
    'http_req_duration{type:lineage,depth:3}': ['p(95)<500'],
    'http_req_duration{type:lineage,depth:4}': ['p(95)<500'],
  },
};

function getJson(url, tags) {
  const response = http.get(url, { timeout: '10s', tags: tags });
  if (response.status !== 200) {
    return null;
  }
  try {
    return response.json();
  } catch (error) {
    return null;
  }
}

export function setup() {
  const nodeIds = new Set();
  const edges = [];
  const edgeKeys = new Set();

  for (const term of SEARCH_TERMS) {
    const payload = getJson(
      `${BASE}/api/search?q=${encodeURIComponent(term)}`,
      { type: 'setup' }
    );
    if (!payload) {
      continue;
    }
    for (const item of payload.results || []) {
      nodeIds.add(item.id);
    }
  }

  if (nodeIds.size === 0) {
    throw new Error('стенд пуст: загрузите данные (make seed)');
  }

  for (const nodeId of Array.from(nodeIds).slice(0, 3)) {
    const separator = nodeId.indexOf(':');
    if (separator <= 0) {
      continue;
    }
    const kind = nodeId.slice(0, separator);
    const key = nodeId.slice(separator + 1);
    const payload = getJson(
      `${BASE}/api/lineage/${kind}/${encodeURIComponent(key)}?direction=both&depth=3`,
      { type: 'setup' }
    );
    if (!payload) {
      continue;
    }
    for (const node of payload.nodes || []) {
      nodeIds.add(node.id);
    }
    for (const edge of payload.edges || []) {
      const pair = `${edge.source}\n${edge.target}`;
      if (!edgeKeys.has(pair)) {
        edgeKeys.add(pair);
        edges.push({ from: edge.source, to: edge.target });
      }
    }
  }

  if (edges.length === 0) {
    throw new Error('не удалось собрать рёбра lineage: загрузите данные (make seed)');
  }

  return { nodes: Array.from(nodeIds), edges: edges, queries: SEARCH_TERMS };
}

function pick(values) {
  return values[Math.floor(Math.random() * values.length)];
}

function record(response, type, depth) {
  if (response.status === 0) {
    networkErrors.add(1);
  } else if (response.status >= 500) {
    serverErrors.add(1);
  }
  const duration = response.timings.duration;
  typeDuration[type].add(duration);
  if (type === 'lineage' && depthDuration[depth]) {
    depthDuration[depth].add(duration);
  }
  check(response, { 'status 200': (r) => r.status === 200 });
}

export default function (data) {
  const roll = Math.random();

  if (roll < 0.6) {
    const nodeId = pick(data.nodes);
    const separator = nodeId.indexOf(':');
    const kind = nodeId.slice(0, separator);
    const key = nodeId.slice(separator + 1);
    const direction = Math.random() < 0.5 ? 'up' : 'down';
    const depth = 2 + Math.floor(Math.random() * 5);
    const response = http.get(
      `${BASE}/api/lineage/${kind}/${encodeURIComponent(key)}` +
        `?direction=${direction}&depth=${depth}`,
      { timeout: '5s', tags: { type: 'lineage', depth: String(depth) } }
    );
    record(response, 'lineage', depth);
    return;
  }

  if (roll < 0.85) {
    const edge = pick(data.edges);
    const response = http.get(
      `${BASE}/api/path?from=${encodeURIComponent(edge.from)}` +
        `&to=${encodeURIComponent(edge.to)}`,
      { timeout: '5s', tags: { type: 'path' } }
    );
    record(response, 'path');
    return;
  }

  const query = pick(data.queries);
  const response = http.get(
    `${BASE}/api/search?q=${encodeURIComponent(query)}`,
    { timeout: '5s', tags: { type: 'search' } }
  );
  record(response, 'search');
}