import http from 'k6/http';
import { check } from 'k6';
import { Trend, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const TEST_EMAIL = __ENV.TEST_EMAIL || 'manish.soni@dynatechconsultancy.com';
const TEST_PASSWORD = __ENV.TEST_PASSWORD || '123456';

// Per-endpoint metrics
const dashboardTime = new Trend('endpoint_dashboard');
const automationTime = new Trend('endpoint_automation');
const rfpDetailsTime = new Trend('endpoint_rfp_details');
const sessionTime = new Trend('endpoint_session');
const logsTime = new Trend('endpoint_logs');
const loginTime = new Trend('endpoint_login');

const endpointErrors = new Counter('endpoint_errors');

export const options = {
  scenarios: {
    // Test each endpoint separately with 20 concurrent users
    dashboard: {
      executor: 'constant-vus',
      vus: 20,
      duration: '30s',
      exec: 'testDashboard',
      tags: { endpoint: 'dashboard' },
    },
    automation: {
      executor: 'constant-vus',
      vus: 20,
      duration: '30s',
      startTime: '35s',
      exec: 'testAutomation',
      tags: { endpoint: 'automation' },
    },
    rfp_details: {
      executor: 'constant-vus',
      vus: 20,
      duration: '30s',
      startTime: '70s',
      exec: 'testRfpDetails',
      tags: { endpoint: 'rfp_details' },
    },
    session: {
      executor: 'constant-vus',
      vus: 20,
      duration: '30s',
      startTime: '105s',
      exec: 'testSession',
      tags: { endpoint: 'session' },
    },
    logs: {
      executor: 'constant-vus',
      vus: 20,
      duration: '30s',
      startTime: '140s',
      exec: 'testLogs',
      tags: { endpoint: 'logs' },
    },
  },
  thresholds: {
    endpoint_dashboard: ['p(95)<2000', 'avg<1000'],
    endpoint_automation: ['p(95)<500', 'avg<200'],
    endpoint_rfp_details: ['p(95)<2000', 'avg<1000'],
    endpoint_session: ['p(95)<500', 'avg<200'],
    endpoint_logs: ['p(95)<1000', 'avg<500'],
  },
};

// Helper function to login and return success status
function doLogin() {
  const loginRes = http.post(`${BASE_URL}/api/login`,
    JSON.stringify({
      email: TEST_EMAIL,
      password: TEST_PASSWORD
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  loginTime.add(loginRes.timings.duration);
  return loginRes.status === 200;
}

// Helper function to logout
function doLogout() {
  http.post(`${BASE_URL}/api/logout`);
}

export function setup() {
  console.log('Running API endpoint throughput tests...');
  console.log(`Target: ${BASE_URL}`);
  console.log(`Test user: ${TEST_EMAIL}`);
}

export function testDashboard() {
  if (!doLogin()) {
    endpointErrors.add(1);
    return;
  }

  const res = http.get(`${BASE_URL}/api/dashboard/data`);
  dashboardTime.add(res.timings.duration);

  const passed = check(res, {
    'dashboard OK': (r) => r.status === 200,
    'dashboard has content': (r) => r.body && r.body.length > 2,
  });

  if (!passed) endpointErrors.add(1);
  doLogout();
}

export function testAutomation() {
  // Automation endpoint doesn't require auth
  const res = http.get(`${BASE_URL}/api/automation/status`);
  automationTime.add(res.timings.duration);

  const passed = check(res, {
    'automation OK': (r) => r.status === 200
  });

  if (!passed) endpointErrors.add(1);
}

export function testRfpDetails() {
  if (!doLogin()) {
    endpointErrors.add(1);
    return;
  }

  // Test with different filters
  const statuses = ['open', 'submitted', 'declined'];
  const status = statuses[Math.floor(Math.random() * statuses.length)];

  const res = http.get(`${BASE_URL}/api/dashboard/rfp-details?status=${status}`);
  rfpDetailsTime.add(res.timings.duration);

  const passed = check(res, {
    'rfp details OK': (r) => r.status === 200
  });

  if (!passed) endpointErrors.add(1);
  doLogout();
}

export function testSession() {
  if (!doLogin()) {
    endpointErrors.add(1);
    return;
  }

  const res = http.get(`${BASE_URL}/api/session/status`);
  sessionTime.add(res.timings.duration);

  const passed = check(res, {
    'session OK': (r) => r.status === 200,
    'session valid': (r) => {
      try {
        return JSON.parse(r.body).valid === true;
      } catch (e) {
        return false;
      }
    }
  });

  if (!passed) endpointErrors.add(1);
  doLogout();
}

export function testLogs() {
  if (!doLogin()) {
    endpointErrors.add(1);
    return;
  }

  // Test with pagination
  const page = Math.floor(Math.random() * 5) + 1;

  const res = http.get(`${BASE_URL}/api/dashboard/view-logs?page=${page}&page_size=20`);
  logsTime.add(res.timings.duration);

  const passed = check(res, {
    'logs OK': (r) => r.status === 200
  });

  if (!passed) endpointErrors.add(1);
  doLogout();
}

// Custom summary showing per-endpoint metrics
export function handleSummary(data) {
  const metrics = data.metrics;

  let output = '\n';
  output += '╔═══════════════════════════════════════════════════════════════════════════╗\n';
  output += '║                      API ENDPOINT PERFORMANCE REPORT                       ║\n';
  output += '╠═══════════════════════════════════════════════════════════════════════════╣\n';
  output += '║ Endpoint                  │   Avg   │   P95   │   P99   │  Max   │ Status ║\n';
  output += '╠═══════════════════════════════════════════════════════════════════════════╣\n';

  const endpoints = [
    { name: 'Dashboard Data', metric: 'endpoint_dashboard', threshold: 2000 },
    { name: 'Automation Status', metric: 'endpoint_automation', threshold: 500 },
    { name: 'RFP Details', metric: 'endpoint_rfp_details', threshold: 2000 },
    { name: 'Session Status', metric: 'endpoint_session', threshold: 500 },
    { name: 'View Logs', metric: 'endpoint_logs', threshold: 1000 },
  ];

  endpoints.forEach(ep => {
    const m = metrics[ep.metric];
    if (m) {
      const avg = Math.round(m.values.avg || 0);
      const p95 = Math.round(m.values['p(95)'] || 0);
      const p99 = Math.round(m.values['p(99)'] || 0);
      const max = Math.round(m.values.max || 0);
      const status = p95 <= ep.threshold ? '  PASS  ' : '  FAIL  ';

      output += `║ ${ep.name.padEnd(25)}│ ${String(avg + 'ms').padStart(7)}│ ${String(p95 + 'ms').padStart(7)}│ ${String(p99 + 'ms').padStart(7)}│ ${String(max + 'ms').padStart(6)}│${status}║\n`;
    }
  });

  output += '╠═══════════════════════════════════════════════════════════════════════════╣\n';

  const totalReqs = (metrics.http_reqs && metrics.http_reqs.values && metrics.http_reqs.values.count) || 0;
  const rps = (metrics.http_reqs && metrics.http_reqs.values && metrics.http_reqs.values.rate) || 0;

  output += `║ Total Requests: ${String(totalReqs).padStart(8)}    │    Throughput: ${String(rps.toFixed(2) + ' req/s').padStart(14)}         ║\n`;
  output += '╚═══════════════════════════════════════════════════════════════════════════╝\n';

  return { stdout: output };
}
