@echo off
title SmartFlow OR - Pytest Verification Suite
echo ========================================================
echo       Running SmartFlow OR Unit Tests (Pytest)
echo ========================================================
echo.
python -m pytest tests -v
echo.
echo ========================================================
echo Test execution complete.
echo ========================================================
pause

