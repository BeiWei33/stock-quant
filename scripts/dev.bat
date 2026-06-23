@echo off
REM Development script for Personal Quant Web Console
REM Starts both FastAPI backend and Vite frontend dev server

echo ==========================================
echo  Personal Quant Web Console - Dev Mode
echo ==========================================
echo.

REM Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Python not found
    exit /b 1
)

REM Check Node.js
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Node.js not found
    exit /b 1
)

REM Install Python dependencies if needed
echo Checking Python dependencies...
pip install fastapi uvicorn python-jose passlib python-multipart pyyaml 2>nul

REM Install frontend dependencies if needed
echo Checking frontend dependencies...
cd /d "%~dp0..\frontend"
if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install
)

REM Start FastAPI backend
echo.
echo Starting FastAPI backend on port 8000...
cd /d "%~dp0.."
start "FastAPI Backend" python -m quant.apps.web --port 8000

REM Wait for backend to start
timeout /t 2 /nobreak >nul

REM Start Vite frontend
echo Starting Vite frontend on port 5173...
cd /d "%~dp0..\frontend"
start "Vite Frontend" npm run dev

echo.
echo ==========================================
echo  Services started!
echo ==========================================
echo  Frontend: http://localhost:5173
echo  Backend:  http://localhost:8000
echo  API Docs: http://localhost:8000/docs
echo ==========================================
echo.
echo Press any key to stop all services
pause >nul

REM Cleanup
taskkill /FI "WindowTitle eq FastAPI Backend*" /F >nul 2>nul
taskkill /FI "WindowTitle eq Vite Frontend*" /F >nul 2>nul
