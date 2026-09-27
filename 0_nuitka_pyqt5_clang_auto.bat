@echo off
rem Nuitka standalone build script for this PyQt5 project.
rem Keep this file ASCII-only: cmd.exe parses .bat byte-wise.

cd /d "%~dp0"

rem The link step fails when the previous exe is still running (file locked).
powershell -NoProfile -Command "if (Get-Process -Name Image_To_Icon_Converter -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [ERROR] Image_To_Icon_Converter.exe is still running. Close it, then build again.
    exit /b 1
)

nuitka --standalone ^
    --enable-plugin=pyqt5 ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=icon.ico ^
    --include-data-files=icon.ico=icon.ico ^
    --follow-imports ^
    --jobs=4 ^
    --clang ^
    --remove-output ^
    --output-dir=build_output ^
    Image_To_Icon_Converter.py

echo.
echo [DONE] Output folder: build_output\Image_To_Icon_Converter.dist\

