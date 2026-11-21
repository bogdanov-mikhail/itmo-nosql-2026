import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const httpErrors = new Counter('http_errors');
const networkErrors = new Counter('network_errors');
const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
const runId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;

export const options = {
  scenarios: {
    default: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: __ENV.SMOKE === '1'
        ? [{ duration: '1s', target: 1 }]
        : [{ duration: '30s', target: 4 }, { duration: '180s', target: 4 }],
    },
  },
  thresholds: { checks: ['rate==1'] },
};

export default function () {
  let payload = '';
  for (let i = 0; i < 40; i++) {
    payload += alphabet[Math.floor(Math.random() * alphabet.length)];
  }
  const target = __ENV.TARGET_URL || 'http://nginx/';
  const separator = target.includes('?') ? '&' : '?';
  const response = http.get(`${target}${separator}cb=${runId}-${__VU}-${__ITER}&p=${payload}`, {
    timeout: '5s',
    tags: { name: 'nginx' },
  });
  if (response.status === 0) {
    networkErrors.add(1);
  } else if (response.status !== 200) {
    httpErrors.add(1, { status: String(response.status) });
  }
  check(response, { 'HTTP 200': (r) => r.status === 200 });
}
