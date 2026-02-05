# Performance Test Runner with Result Storage
# Usage: .\run-tests.ps1 -TestType smoke|load|stress|api|all

param(
    [Parameter(Position=0)]
    [ValidateSet("smoke", "load", "stress", "api", "all")]
    [string]$TestType = "smoke"
)

$ErrorActionPreference = "Continue"

# Get current timestamp
$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm"

# Set paths
$ScriptDir = Join-Path $PSScriptRoot "scripts"
$ResultsDir = Join-Path $PSScriptRoot "results"

# Create results directory if not exists
if (!(Test-Path $ResultsDir)) {
    New-Item -ItemType Directory -Path $ResultsDir | Out-Null
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RFP Performance Test Runner" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test Type: $TestType" -ForegroundColor Yellow
Write-Host "Timestamp: $Timestamp"
Write-Host "Results: $ResultsDir"
Write-Host ""

function Run-Test {
    param([string]$Name, [string]$Script, [string]$Description)

    Write-Host "Running $Name..." -ForegroundColor Green
    Write-Host $Description -ForegroundColor Gray
    Write-Host ""

    $JsonFile = Join-Path $ResultsDir "${Name}_${Timestamp}.json"
    $SummaryFile = Join-Path $ResultsDir "${Name}_${Timestamp}_summary.txt"

    # Run k6 and capture output
    $output = k6 run --out json="$JsonFile" "$Script" 2>&1 | Tee-Object -Variable k6Output

    # Save summary to text file
    $k6Output | Out-File -FilePath $SummaryFile -Encoding UTF8

    Write-Host ""
    Write-Host "Results saved:" -ForegroundColor Green
    Write-Host "  JSON: $JsonFile"
    Write-Host "  Summary: $SummaryFile"
    Write-Host ""
}

switch ($TestType) {
    "smoke" {
        Run-Test -Name "smoke" -Script "$ScriptDir\smoke-test.js" -Description "Quick validation (1 min, 5 users)"
    }
    "load" {
        Run-Test -Name "load" -Script "$ScriptDir\load-test.js" -Description "Standard load test (21 min, 50-150 users)"
    }
    "stress" {
        Run-Test -Name "stress" -Script "$ScriptDir\stress-test.js" -Description "Stress test (16 min, up to 300 users)"
    }
    "api" {
        Run-Test -Name "api" -Script "$ScriptDir\api-endpoints.js" -Description "API endpoint test (3 min per endpoint)"
    }
    "all" {
        Write-Host "Running ALL tests sequentially..." -ForegroundColor Magenta
        Write-Host ""

        Run-Test -Name "smoke" -Script "$ScriptDir\smoke-test.js" -Description "[1/4] Quick validation"
        Run-Test -Name "api" -Script "$ScriptDir\api-endpoints.js" -Description "[2/4] API endpoints"
        Run-Test -Name "load" -Script "$ScriptDir\load-test.js" -Description "[3/4] Load test"
        Run-Test -Name "stress" -Script "$ScriptDir\stress-test.js" -Description "[4/4] Stress test"

        Write-Host "All tests completed!" -ForegroundColor Green
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Test Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# List recent results
Write-Host "Recent results in $ResultsDir :" -ForegroundColor Yellow
Get-ChildItem $ResultsDir -Filter "*$Timestamp*" | ForEach-Object {
    Write-Host "  - $($_.Name)"
}
