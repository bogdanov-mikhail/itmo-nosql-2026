import http from 'k6/http';
import { Counter, Rate } from 'k6/metrics';

// fair: heavy standard 120 rps + light free 5 rps →
// light 100% 200, heavy ≥ 50% 429 client
const heavyAllowed = new Counter('heavy_allowed');
const heavyRejectedClient = new Counter('heavy_rejected_client');
const lightAllowed = new Counter('light_allowed');
const lightRejected = new Counter('light_rejected');
const heavyRejectShare = new Rate('heavy_reject_share');

export const options = {
  scenarios: {
    heavy: {
      executor: 'constant-arrival-rate',
      rate: 120,
      timeUnit: '1s',
      duration: '20s',
      exec: 'heavyPhase',
      preAllocatedVUs: 30,
      maxVUs: 150,
    },
    light: {
      executor: 'constant-arrival-rate',
      rate: 5,
      timeUnit: '1s',
      duration: '20s',
      exec: 'lightPhase',
      preAllocatedVUs: 5,
      maxVUs: 20,
    },
  },
  thresholds: {
    light_rejected: ['count==0'],
    light_allowed: ['count>=95'],
    heavy_reject_share: ['rate>=0.5'],
    heavy_rejected_client: ['count>0'],
  },
};

function reason(res) {
  for (const [k, v] of Object.entries(res.headers || {})) {
    if (k.toLowerCase() === 'x-rate-limit-reason') return v;
  }
  return null;
}

export function heavyPhase() {
  const res = http.get(`${__ENV.APP_BASE_URL}/courses`, {
    headers: { 'X-API-Key': __ENV.API_KEY_STANDARD },
  });
  if (res.status === 200) {
    heavyAllowed.add(1);
    heavyRejectShare.add(0);
  } else if (res.status === 429 && reason(res) === 'client') {
    heavyRejectedClient.add(1);
    heavyRejectShare.add(1);
  }
}

export function lightPhase() {
  const res = http.get(`${__ENV.APP_BASE_URL}/courses`, {
    headers: { 'X-API-Key': __ENV.API_KEY_FREE },
  });
  if (res.status === 200) lightAllowed.add(1);
  else lightRejected.add(1);
}
