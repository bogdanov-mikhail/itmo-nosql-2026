import http from 'k6/http';
import { check } from 'k6';

// smoke: 1 standard-клиент, 5 rps, 30 s → все 200
export const options = {
  scenarios: {
    smoke: {
      executor: 'constant-arrival-rate',
      rate: 5,
      timeUnit: '1s',
      duration: '30s',
      exec: 'default',
      preAllocatedVUs: 5,
      maxVUs: 20,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.001'],
    checks: ['rate==1.0'],
  },
};

export default function () {
  const res = http.get(`${__ENV.APP_BASE_URL}/courses`, {
    headers: { 'X-API-Key': __ENV.API_KEY_STANDARD },
  });
  check(res, { 'status is 200': (r) => r.status === 200 });
}
