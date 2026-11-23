import http from 'k6/http';
import { Counter } from 'k6/metrics';

// burst: free-клиент: мгновенный burst 30 (capacity 20) → часть 429 client;
// далее 25 rps при rate 10 → steady ~10 rps allowed
const burstAllowed = new Counter('burst_allowed');
const burstRejectedClient = new Counter('burst_rejected_client');
const steadyAllowed = new Counter('steady_allowed');
const steadyRejected = new Counter('steady_rejected');

export const options = {
  scenarios: {
    burst: {
      executor: 'per-vu-iterations',
      vus: 30,
      iterations: 1,
      exec: 'burstPhase',
    },
    steady: {
      executor: 'constant-arrival-rate',
      rate: 25,
      timeUnit: '1s',
      duration: '20s',
      exec: 'steadyPhase',
      startTime: '3s',
      preAllocatedVUs: 10,
      maxVUs: 40,
    },
  },
  thresholds: {
    burst_allowed: ['count>=15'],
    burst_rejected_client: ['count>=5'],
    steady_allowed: ['count>=150', 'count<=280'],
    steady_rejected: ['count>=250'],
  },
};

function reason(res) {
  for (const [k, v] of Object.entries(res.headers || {})) {
    if (k.toLowerCase() === 'x-rate-limit-reason') return v;
  }
  return null;
}

export function burstPhase() {
  const res = http.get(`${__ENV.APP_BASE_URL}/courses`, {
    headers: { 'X-API-Key': __ENV.API_KEY_FREE },
  });
  if (res.status === 200) burstAllowed.add(1);
  else if (res.status === 429 && reason(res) === 'client') burstRejectedClient.add(1);
}

export function steadyPhase() {
  const res = http.get(`${__ENV.APP_BASE_URL}/courses`, {
    headers: { 'X-API-Key': __ENV.API_KEY_FREE },
  });
  if (res.status === 200) steadyAllowed.add(1);
  else if (res.status === 429) steadyRejected.add(1);
}
