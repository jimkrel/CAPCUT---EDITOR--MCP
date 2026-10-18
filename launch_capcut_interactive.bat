@echo off
set "CAPCUT_BASE=%LOCALAPPDATA%\CapCut\Apps"
for /f "delims=" %%I in ('dir /b /ad /o-n "%CAPCUT_BASE%" 2^>nul') do (
    if exist "%CAPCUT_BASE%\%%I\CapCut.exe" (
        cd /d "%CAPCUT_BASE%\%%I"
        start "" "CapCut.exe"
        goto :done
    )
)
if exist "%CAPCUT_BASE%\CapCut.exe" (
    cd /d "%CAPCUT_BASE%"
    start "" "CapCut.exe"
)
:done
