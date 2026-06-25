@echo off
chcp 65001 > nul
setlocal

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set PROJECT_DIR=D:\Git\GitHub\GitHubRepositories\Synoptics

cd /d "%PROJECT_DIR%"

if not exist logs mkdir logs

echo ================================================== >> logs\synoptics_daily.log
echo Started: %date% %time% >> logs\synoptics_daily.log

call C:\Users\fischer.m\miniconda3\Scripts\activate.bat synoptics

python .\src\run_all.py --run "2024-09-12 00:00" --fxx-list "0,6,12,24,48,72,96,120,144,168,192,216,240" --email-report --ai-figure-hours all >> logs\synoptics_daily.log 2>&1

echo Finished: %date% %time% >> logs\synoptics_daily.log
echo Exit code: %ERRORLEVEL% >> logs\synoptics_daily.log

endlocal
exit /b %ERRORLEVEL%