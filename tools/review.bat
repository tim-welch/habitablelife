@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM --- Injected argument handling: if %1 doesn't start with "--" and exists, add --instructions=%1 and shift ---
set "EXTRA="
set "first=%~1"
if not "%first%"=="" (
  set "prefix=%first:~0,2%"
  if /I not "!prefix!"=="--" (
    if exist "%first%" (
      set "EXTRA=--instructions=%~1"
      shift
    )
  )
)

python tools\smartnotes\sm.py --print-context-summary --include-file-names --max-tokens=2000 %EXTRA% %