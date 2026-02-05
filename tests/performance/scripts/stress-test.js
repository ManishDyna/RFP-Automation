import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const TEST_EMAIL = __ENV.TEST_EMAIL || 'manish.soni@dynatechconsultancy.com';
const TEST_PASSWORD = __ENV.TEST_PASSWORD || '123456';

// Custom metrics for stress analysis
const responseTime = new Trend('response_time');
const loginTime = new Trend('login_time');
const errorCount = new Counter('error_count');
const successRate = new Rate('success_rate');

export const options = {
  stages: [
    { duration: '2m', target: 50 },    // Warm up
    { duration: '3m', target: 100 },   // Normal load
    { duration: '3m', target: 200 },   // High load
    { duration: '3m', target: 300 },   // Stress load
    { duration: '3m', target: 300 },   // Stay at stress
    { duration: '2m', target: 0 },     // Recovery
  ],
  thresholds: {
    http_req_duration: ['p(95)<5000'],  // More lenient for stress
    http_req_failed: ['rate<0.15'],     // Allow up to 15% errors under stress
    success_rate: ['rate>0.85'],        // At least 85% success
  },
};

export function setup() {
  console.log('Starting stress test...');
  console.log(`Target: ${BASE_URL}`);
  console.log(`Test user: ${TEST_EMAIL}`);
}

export default function() {
  // Each VU logs in independently
  const loginRes = http.post(`${BASE_URL}/api/login`,
    JSON.stringify({
      email: TEST_EMAIL,
      password: TEST_PASSWORD
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  loginTime.add(loginRes.timings.duration);

  const loginOk = check(loginRes, {
    'login OK': (r) => r.status === 200,
  });

  if (!loginOk) {
    errorCount.add(1);
    successRate.add(false);
    sleep(1);
    return;
  }

  sleep(0.3);

  // Focus on heaviest endpoint to stress the system
  const res = http.get(`${BASE_URL}/api/dashboard/data`);
  responseTime.add(res.timings.duration);

  const passed = check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 5s': (r) => r.timings.duration < 5000,
    'response has body': (r) => r.body && r.body.length > 0,
  });

  successRate.add(passed);
  if (!passed) {
    errorCount.add(1);
    if (__VU % 50 === 0) { // Log every 50th VU to avoid spam
      console.log(`Error at VU ${__VU}: status=${res.status}, time=${res.timings.duration}ms`);
    }
  }

  // Logout
  http.post(`${BASE_URL}/api/logout`);

  sleep(0.5);
}

export function teardown() {
  console.log('Stress test completed.');
}

// Custom summary for stress test
export function handleSummary(data) {
  const metrics = data.metrics;

  let output = '\n';
  output += '╔══════════════════════════════════════════════════════════════╗\n';
  output += '║                    STRESS TEST RESULTS                       ║\n';
  output += '╠══════════════════════════════════════════════════════════════╣\n';

  const totalReqs = (metrics.http_reqs && metrics.http_reqs.values && metrics.http_reqs.values.count) || 0;
  const failedRate = (metrics.http_req_failed && metrics.http_req_failed.values && metrics.http_req_failed.values.rate) || 0;
  const errorRate = (failedRate * 100).toFixed(2);

  output += `║ Total Requests:     ${String(totalReqs).padStart(10)}                        ║\n`;
  output += `║ Error Rate:         ${String(errorRate + '%').padStart(10)}                        ║\n`;
  output += '╠══════════════════════════════════════════════════════════════╣\n';

  const durationVals = (metrics.http_req_duration && metrics.http_req_duration.values) || {};
  const avgTime = Math.round(durationVals.avg || 0);
  const p50Time = Math.round(durationVals['p(50)'] || 0);
  const p95Time = Math.round(durationVals['p(95)'] || 0);
  const p99Time = Math.round(durationVals['p(99)'] || 0);
  const maxTime = Math.round(durationVals.max || 0);

  output += `║ Response Time (avg):    ${String(avgTime + 'ms').padStart(8)}                      ║\n`;
  output += `║ Response Time (p50):    ${String(p50Time + 'ms').padStart(8)}                      ║\n`;
  output += `║ Response Time (p95):    ${String(p95Time + 'ms').padStart(8)}                      ║\n`;
  output += `║ Response Time (p99):    ${String(p99Time + 'ms').padStart(8)}                      ║\n`;
  output += `║ Response Time (max):    ${String(maxTime + 'ms').padStart(8)}                      ║\n`;
  output += '╠══════════════════════════════════════════════════════════════╣\n';

  // Determine system capacity
  let capacity = 'UNKNOWN';
  const errorRateNum = parseFloat(errorRate);
  if (errorRateNum < 1) {
    capacity = '300+ users (EXCELLENT)';
  } else if (errorRateNum < 5) {
    capacity = '200-300 users (GOOD)';
  } else if (errorRateNum < 15) {
    capacity = '100-200 users (ACCEPTABLE)';
  } else {
    capacity = '< 100 users (NEEDS OPTIMIZATION)';
  }

  output += `║ Estimated Capacity: ${capacity.padEnd(38)} ║\n`;
  output += '╚══════════════════════════════════════════════════════════════╝\n';

  return { stdout: output };
}
