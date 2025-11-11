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
    ) else (
      REM Also check ..\prompts\api relative to this script's directory
      set "alt=%~dp0..\prompts\api\%~1"
      if exist "!alt!" (
        set "EXTRA=--instructions=!alt!"
        shift
      ) else (
        REM Try again with .md extension
        set "altmd=%~dp0..\prompts\api\%~1.md"
        if exist "!altmd!" (
          set "EXTRA=--instructions=!altmd!"
          shift
        )
      )
    )
  )
)

echo %EXTRA%
echo %*

python tools\smartnotes\sm.py --print-context-summary --keep-front-matter --include-file-names --max-tokens=2000 "%EXTRA%" %1 %2 %3 %4 %5 %6 %7 %8 %9