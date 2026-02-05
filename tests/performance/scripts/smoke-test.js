import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const TEST_EMAIL = __ENV.TEST_EMAIL || 'manish.soni@dynatechconsultancy.com';
const TEST_PASSWORD = __ENV.TEST_PASSWORD || '123456';

export const options = {
  vus: 5,              // 5 virtual users
  duration: '1m',      // Run for 1 minute
  thresholds: {
    http_req_duration: ['p(95)<2000'],  // 95% requests < 2s
    http_req_failed: ['rate<0.05'],      // Error rate < 5% (more lenient for testing)
  },
};

// Each VU maintains its own session via cookie jar (automatic in k6)
export default function() {
  // Step 1: Login (each VU gets its own session)
  const loginRes = http.post(`${BASE_URL}/api/login`,
    JSON.stringify({
      email: TEST_EMAIL,
      password: TEST_PASSWORD
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );

  const loginOk = check(loginRes, {
    'login status 200': (r) => r.status === 200,
  });

  if (!loginOk) {
    console.error(`Login failed: ${loginRes.status} - ${loginRes.body}`);
    sleep(3);
    return; // Skip this iteration if login failed
  }

  sleep(0.5);

  // Step 2: Test dashboard endpoint
  const dashboardRes = http.get(`${BASE_URL}/api/dashboard/data`);
  check(dashboardRes, {
    'dashboard status 200': (r) => r.status === 200,
    'dashboard response time < 2s': (r) => r.timings.duration < 2000,
    'dashboard has data': (r) => r.body && r.body.length > 10,
  });

  sleep(1);

  // Step 3: Test automation status
  const automationRes = http.get(`${BASE_URL}/api/automation/status`);
  check(automationRes, {
    'automation status 200': (r) => r.status === 200,
  });

  sleep(1);

  // Step 4: Test session status
  const sessionRes = http.get(`${BASE_URL}/api/session/status`);
  check(sessionRes, {
    'session status 200': (r) => r.status === 200,
    'session is valid': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.valid === true;
      } catch (e) {
        return false;
      }
    },
  });

  sleep(1);

  // Step 5: Logout
  http.post(`${BASE_URL}/api/logout`);
}
