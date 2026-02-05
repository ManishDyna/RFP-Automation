# Performance Testing - RFP Automation System

This directory contains k6 performance tests for the RFP Automation System.

## Prerequisites

### Install k6

**Windows (Chocolatey):**

```bash
choco install k6
```

**Windows (Winget):**

```bash
winget install k6
```

**Download directly:** https://k6.io/docs/get-started/installation/

## Test Scripts

| Script               | Purpose              | Users       | Duration   |
| -------------------- | -------------------- | ----------- | ---------- |
| `smoke-test.js`    | Quick validation     | 5           | 1 min      |
| `load-test.js`     | Normal operation     | 50-150      | 21 min     |
| `stress-test.js`   | Find breaking point  | 50-300      | 16 min     |
| `api-endpoints.js` | Per-endpoint metrics | 20/endpoint | 3 min each |

## Quick Start

### 1. Start the Backend Server

```bash
cd c:\python\RFP-automation
python dashboard_main.py
```

### 2. Run Tests with Result Storage (Recommended)

Use the provided scripts to automatically save results with timestamps:

**PowerShell (Recommended):**

```powershell
cd tests/performance

# Run smoke test
.\run-tests.ps1 smoke

# Run load test
.\run-tests.ps1 load

# Run all tests
.\run-tests.ps1 all
```

**Command Prompt:**

```cmd
cd tests\performance

# Run smoke test
run-tests.bat smoke

# Run load test
run-tests.bat load

# Run all tests
run-tests.bat all
```

Results are saved to `tests/performance/results/` with timestamps:
- `smoke_2024-02-05_14-30.json` - Raw k6 metrics
- `smoke_2024-02-05_14-30_summary.txt` - Console output summary

### 3. Run Tests Manually (Without Saving)

```bash
k6 run tests/performance/scripts/smoke-test.js
```

## Configuration

### Environment Variables

| Variable          | Default               | Description        |
| ----------------- | --------------------- | ------------------ |
| `BASE_URL`      | http://localhost:8000 | Backend server URL |
| `TEST_EMAIL`    | test@example.com      | Test user email    |
| `TEST_PASSWORD` | testpassword          | Test user password |

### Example with Custom Config

```bash
k6 run -e BASE_URL=http://192.168.1.100:8000 -e TEST_EMAIL=admin@test.com -e TEST_PASSWORD=secret123 tests/performance/scripts/load-test.js
```

## Test Descriptions

### Smoke Test (`smoke-test.js`)

Quick sanity check to validate the test setup works correctly.

**What it tests:**

- Login/logout flow
- Dashboard data endpoint
- Automation status endpoint
- Session status endpoint

**Run:**

```bash
k6 run tests/performance/scripts/smoke-test.js
```

---

### Load Test (`load-test.js`)

Simulates normal production load with gradual user ramp-up.

**Stages:**

1. 0-2 min: Ramp to 50 users
2. 2-7 min: Stay at 50 users
3. 7-9 min: Ramp to 100 users
4. 9-14 min: Stay at 100 users
5. 14-16 min: Ramp to 150 users
6. 16-19 min: Stay at 150 users
7. 19-21 min: Ramp down to 0

**Thresholds:**

- p95 response time < 3 seconds
- p99 response time < 5 seconds
- Error rate < 1%
- Dashboard p95 < 2 seconds

**Run:**

```bash
k6 run tests/performance/scripts/load-test.js
```

---

### Stress Test (`stress-test.js`)

Finds the breaking point by gradually increasing load beyond expected capacity.

**Stages:**

1. Warm-up: 50 users (2 min)
2. Normal: 100 users (3 min)
3. High: 200 users (3 min)
4. Stress: 300 users (6 min)
5. Recovery: 0 users (2 min)

**Thresholds (lenient for stress):**

- p95 response time < 5 seconds
- Error rate < 10%

**Run:**

```bash
k6 run tests/performance/scripts/stress-test.js
```

---

### API Endpoints Test (`api-endpoints.js`)

Tests each endpoint individually to get precise per-endpoint metrics.

**Endpoints tested:**

| Endpoint          | Threshold (p95) |
| ----------------- | --------------- |
| Dashboard Data    | < 2000ms        |
| Automation Status | < 500ms         |
| RFP Details       | < 2000ms        |
| Session Status    | < 200ms         |
| View Logs         | < 1000ms        |

**Run:**

```bash
k6 run tests/performance/scripts/api-endpoints.js
```

## Output & Reports

### Results Directory Structure

```
tests/performance/
├── scripts/              # Test scripts
├── results/              # Test results (auto-generated)
│   ├── smoke_2024-02-05_14-30.json
│   ├── smoke_2024-02-05_14-30_summary.txt
│   ├── load_2024-02-05_14-45.json
│   └── ...
├── run-tests.ps1         # PowerShell runner
├── run-tests.bat         # Batch runner
└── README.md
```

### Save Results Manually

**JSON Output (detailed metrics):**

```bash
k6 run --out json=results/mytest.json tests/performance/scripts/load-test.js
```

**CSV Output (spreadsheet-friendly):**

```bash
k6 run --out csv=results/mytest.csv tests/performance/scripts/load-test.js
```

### InfluxDB (for Grafana dashboards)

```bash
k6 run --out influxdb=http://localhost:8086/k6 tests/performance/scripts/load-test.js
```

## Performance Thresholds

| Metric              | Good   | Warning | Critical |
| ------------------- | ------ | ------- | -------- |
| Response Time (p95) | < 1s   | 1s-3s   | > 3s     |
| Response Time (p99) | < 2s   | 2s-5s   | > 5s     |
| Error Rate          | < 0.1% | 0.1%-1% | > 1%     |
| Throughput (RPS)    | > 100  | 50-100  | < 50     |

## Troubleshooting

### Login Fails

1. Ensure the backend is running
2. Check test credentials are correct
3. Verify the BASE_URL is accessible

### High Error Rate

1. Check backend logs for errors
2. Verify database connections
3. Monitor server resources (CPU, memory)

### Slow Response Times

1. Check Dataverse API latency
2. Review backend cache settings
3. Monitor database query performance

## Recommended Test Order

1. **Smoke Test** - Validate setup
2. **API Endpoints Test** - Baseline per-endpoint metrics
3. **Load Test** - Normal production simulation
4. **Stress Test** - Find capacity limits

## Known System Bottlenecks

Based on code analysis, these are pre-identified concerns:

1. **Dashboard Data** - Fetches 5000 rows from Dataverse
2. **iterrows() Pattern** - Slow pandas iteration
3. **5-minute Cache** - May cause burst loads after TTL
4. **No Rate Limiting** - Login vulnerable to brute force
