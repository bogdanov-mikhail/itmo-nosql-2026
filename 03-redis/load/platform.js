import http from 'k6/http';
import { Counter } from 'k6/metrics';

// platform: суммарно 480 rps при глобальной квоте 300 →
// 429 platform присутствуют, 5xx отсутствуют.
// Требует повышенного тарифа per-client на время прогона (make load PROFILE=platform
// поднимает app с RATELIMIT_STANDARD_RATE=1000, иначе client-лимит не пустит дальше 50 rps
// и глобальная квота никогда не сработает).
const allowed = new Counter('platform_allowed');
const rejectedPlatform = new Counter('rejected_platform');
const rejectedClient = new Counter('rejected_client');
const serverErrors = new Counter('server_errors');

const VUS = 8;
const RATE_PER_VU = 60;

function scenario(name) {
  return {
    executor: 'constant-arrival-rate',
    rate: RATE_PER_VU,
    timeUnit: '1s',
    duration: '20s',
    exec: 'default',
    preAllocatedVUs: 15,
    maxVUs: 70,
    tags: { client: name },
  };
}

export const options = {
  scenarios: Object.fromEntries(Array.from({ length: VUS }, (_, i) => [`client${i}`, scenario(`client${i}`)])),
  thresholds: {
    rejected_platform: ['count>0'],
    rejected_client: ['count==0'],
    server_errors: ['count==0'],
    platform_allowed: ['count>0'],
  },
};

function reason(res) {
  for (const [k, v] of Object.entries(res.headers || {})) {
    if (k.toLowerCase() === 'x-rate-limit-reason') return v;
  }
  return null;
}

export default function () {
  const res = http.get(`${__ENV.APP_BASE_URL}/courses`, {
    headers: { 'X-API-Key': __ENV.API_KEY_STANDARD },
  });
  if (res.status === 200) allowed.add(1);
  else if (res.status === 429 && reason(res) === 'platform') rejectedPlatform.add(1);
  else if (res.status === 429 && reason(res) === 'client') rejectedClient.add(1);
  else if (res.status >= 500) serverErrors.add(1);
}
