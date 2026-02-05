import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const TEST_EMAIL = __ENV.TEST_EMAIL || 'manish.soni@dynatechconsultancy.com';
const TEST_PASSWORD = __ENV.TEST_PASSWORD || '123456';

// Custom metrics
const dashboardDuration = new Trend('dashboard_duration');
const automationDuration = new Trend('automation_duration');
const rfpDetailsDuration = new Trend('rfp_details_duration');
const loginDuration = new Trend('login_duration');
const apiErrors = new Counter('api_errors');
const successRate = new Rate('success_rate');

export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up to 50 users
    { duration: '5m', target: 50 },   // Stay at 50 users
    { duration: '2m', target: 100 },  // Ramp up to 100 users
    { duration: '5m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 150 },  // Ramp up to 150 users
    { duration: '3m', target: 150 },  // Stay at 150 users
    { duration: '2m', target: 0 },    // Ramp down to 0
  ],
  thresholds: {
    http_req_duration: ['p(95)<3000', 'p(99)<5000'],
    http_req_failed: ['rate<0.05'],
    dashboard_duration: ['p(95)<2000'],
    automation_duration: ['p(95)<500'],
    login_duration: ['p(95)<1000'],
    success_rate: ['rate>0.90'],
  },
};

export default function() {
  // Each VU logs in and maintains its own session
  group('Authentication', function() {
    const loginRes = http.post(`${BASE_URL}/api/login`,
      JSON.stringify({
        email: TEST_EMAIL,
        password: TEST_PASSWORD
      }),
      { headers: { 'Content-Type': 'application/json' } }
    );
    loginDuration.add(loginRes.timings.duration);

    const loginOk = check(loginRes, {
      'login OK': (r) => r.status === 200,
    });
    successRate.add(loginOk);

    if (!loginOk) {
      apiErrors.add(1);
      console.error(`Login failed: ${loginRes.status}`);
      sleep(3);
      return;
    }
  });

  sleep(0.5);

  group('Dashboard Operations', function() {
    // Main dashboard - HEAVIEST endpoint
    const dashRes = http.get(`${BASE_URL}/api/dashboard/data`);
    dashboardDuration.add(dashRes.timings.duration);

    const dashCheck = check(dashRes, {
      'dashboard OK': (r) => r.status === 200,
      'dashboard has data': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body !== null;
        } catch (e) {
          return false;
        }
      },
    });
    successRate.add(dashCheck);
    if (!dashCheck) apiErrors.add(1);

    sleep(Math.random() * 2 + 1); // 1-3 seconds
  });

  group('Automation Status', function() {
    // Polled frequently
    const statusRes = http.get(`${BASE_URL}/api/automation/status`);
    automationDuration.add(statusRes.timings.duration);

    const statusCheck = check(statusRes, {
      'automation status OK': (r) => r.status === 200
    });
    successRate.add(statusCheck);
    if (!statusCheck) apiErrors.add(1);

    sleep(1);
  });

  group('RFP Operations', function() {
    // RFP details with filter
    const rfpRes = http.get(`${BASE_URL}/api/dashboard/rfp-details?status=open`);
    rfpDetailsDuration.add(rfpRes.timings.duration);

    const rfpCheck = check(rfpRes, {
      'rfp details OK': (r) => r.status === 200
    });
    successRate.add(rfpCheck);
    if (!rfpCheck) apiErrors.add(1);

    sleep(Math.random() * 2 + 1);
  });

  group('Session Check', function() {
    const sessionRes = http.get(`${BASE_URL}/api/session/status`);
    const sessionCheck = check(sessionRes, {
      'session OK': (r) => r.status === 200
    });
    successRate.add(sessionCheck);
  });

  // Logout at end of iteration
  http.post(`${BASE_URL}/api/logout`);

  sleep(Math.random() * 2 + 1); // 1-3 seconds between iterations
}
