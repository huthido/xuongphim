@echo off
rem Mở Xưởng phim trên Windows: bấm đúp file này. Tắt bằng cách đóng cửa sổ đen.
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
if exist "..\long_tieng\env\Scripts\python.exe" set "PY=..\long_tieng\env\Scripts\python.exe"
if not defined PY if exist "..\tao_video\env\Scripts\python.exe" set "PY=..\tao_video\env\Scripts\python.exe"
if not defined PY where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo Khong tim thay Python 3.9+. Cai bang: winget install Python.Python.3.12
  pause
  exit /b 1
)
%PY% -I xuong_phim.py %*
pause
