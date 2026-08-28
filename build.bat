@echo off
chcp 65001 >nul
title EdgeSRT-Desktop 打包工具

echo ====================================================
echo   Edge 即時語音轉錄桌面工具 - 一鍵單文件編譯
echo ====================================================
echo.

cd /d "%~dp0"

echo [1/3] 清理舊的編譯快取...
if exist "build" rd /s /q "build"
if exist "dist\EdgeSRT-Desktop.exe" del /f /q "dist\EdgeSRT-Desktop.exe"

echo.
echo [2/3] 正在使用 PyInstaller 進行打包 (請稍候 30~60 秒)...
pyinstaller --noconfirm --onefile --windowed --noupx ^
  --name "EdgeSRT-Desktop" ^
  --icon "assets/app_icon.ico" ^
  --add-data "capturer;capturer" ^
  --add-data "bin;bin" ^
  --hidden-import "comtypes" ^
  --hidden-import "aiohttp" ^
  --hidden-import "win32gui" ^
  --hidden-import "win32con" ^
  --hidden-import "win32process" ^
  main.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ====================================================
    echo   [成功] 單文件 EXE 編譯完成！
    echo   輸出路徑: %~dp0dist\EdgeSRT-Desktop.exe
    echo ====================================================
) else (
    echo.
    echo ====================================================
    echo   [失敗] 打包過程發生錯誤，請檢查上方日誌！
    echo ====================================================
)

echo.
pause
