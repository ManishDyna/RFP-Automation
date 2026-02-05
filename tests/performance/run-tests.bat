@echo off
REM Performance Test Runner with Result Storage
REM Usage: run-tests.bat [smoke|load|stress|api|all]

setlocal enabledelayedexpansion

REM Get current timestamp for result files
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /format:list') do set datetime=%%I
set TIMESTAMP=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%_%datetime:~8,2%-%datetime:~10,2%

REM Set paths
set SCRIPT_DIR=%~dp0scripts
set RESULTS_DIR=%~dp0results

REM Create results directory if not exists
if not exist "%RESULTS_DIR%" mkdir "%RESULTS_DIR%"

REM Check argument
set TEST_TYPE=%1
if "%TEST_TYPE%"=="" set TEST_TYPE=smoke

echo.
echo ========================================
echo  RFP Performance Test Runner
echo ========================================
echo.
echo Test Type: %TEST_TYPE%
echo Timestamp: %TIMESTAMP%
echo Results will be saved to: %RESULTS_DIR%
echo.

if "%TEST_TYPE%"=="smoke" goto :smoke
if "%TEST_TYPE%"=="load" goto :load
if "%TEST_TYPE%"=="stress" goto :stress
if "%TEST_TYPE%"=="api" goto :api
if "%TEST_TYPE%"=="all" goto :all
goto :usage

:smoke
echo Running Smoke Test...
k6 run --out json="%RESULTS_DIR%\smoke_%TIMESTAMP%.json" "%SCRIPT_DIR%\smoke-test.js"
echo Results saved to: %RESULTS_DIR%\smoke_%TIMESTAMP%.json
goto :end

:load
echo Running Load Test (this will take ~21 minutes)...
k6 run --out json="%RESULTS_DIR%\load_%TIMESTAMP%.json" "%SCRIPT_DIR%\load-test.js"
echo Results saved to: %RESULTS_DIR%\load_%TIMESTAMP%.json
goto :end

:stress
echo Running Stress Test (this will take ~16 minutes)...
k6 run --out json="%RESULTS_DIR%\stress_%TIMESTAMP%.json" "%SCRIPT_DIR%\stress-test.js"
echo Results saved to: %RESULTS_DIR%\stress_%TIMESTAMP%.json
goto :end

:api
echo Running API Endpoints Test (this will take ~3 minutes)...
k6 run --out json="%RESULTS_DIR%\api_%TIMESTAMP%.json" "%SCRIPT_DIR%\api-endpoints.js"
echo Results saved to: %RESULTS_DIR%\api_%TIMESTAMP%.json
goto :end

:all
echo Running ALL tests...
echo.
echo [1/4] Smoke Test...
k6 run --out json="%RESULTS_DIR%\smoke_%TIMESTAMP%.json" "%SCRIPT_DIR%\smoke-test.js"
echo.
echo [2/4] API Endpoints Test...
k6 run --out json="%RESULTS_DIR%\api_%TIMESTAMP%.json" "%SCRIPT_DIR%\api-endpoints.js"
echo.
echo [3/4] Load Test...
k6 run --out json="%RESULTS_DIR%\load_%TIMESTAMP%.json" "%SCRIPT_DIR%\load-test.js"
echo.
echo [4/4] Stress Test...
k6 run --out json="%RESULTS_DIR%\stress_%TIMESTAMP%.json" "%SCRIPT_DIR%\stress-test.js"
echo.
echo All tests completed! Results saved to: %RESULTS_DIR%
goto :end

:usage
echo.
echo Usage: run-tests.bat [smoke^|load^|stress^|api^|all]
echo.
echo   smoke  - Quick validation test (1 min, 5 users)
echo   load   - Standard load test (21 min, 50-150 users)
echo   stress - Stress test (16 min, up to 300 users)
echo   api    - API endpoint test (3 min, 20 users per endpoint)
echo   all    - Run all tests sequentially
echo.
goto :end

:end
echo.
echo ========================================
echo  Test Complete
echo ========================================
endlocal
