@echo off
chcp 65001 >nul
echo.
echo  🚀 Music Tab Finder - 部署到 GitHub Pages
echo  ════════════════════════════════════════════
echo.

:: 取得腳本所在目錄
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

:: Step 1: 匯出樂譜資料
echo  📦 Step 1: 匯出樂譜資料...
if exist "backend\history.json" (
    copy /y "backend\history.json" "frontend\data\sheets.json" >nul
    echo     ✅ 已匯出 history.json → frontend\data\sheets.json
) else (
    echo     ⚠️ 尚無歷史資料 (backend\history.json 不存在)
    echo     將部署空的樂譜庫
)
echo.

:: Step 2: 部署到 gh-pages 分支
echo  🌐 Step 2: 部署到 GitHub Pages...

:: 建立臨時目錄
set "TEMP_DEPLOY=%TEMP%\music-tab-finder-deploy"
if exist "%TEMP_DEPLOY%" rmdir /s /q "%TEMP_DEPLOY%"
mkdir "%TEMP_DEPLOY%"

:: 複製前端檔案
xcopy /s /e /q "frontend\*" "%TEMP_DEPLOY%\" >nul

:: 切換到臨時目錄進行 git 操作
cd /d "%TEMP_DEPLOY%"
git init >nul 2>&1
git checkout -b gh-pages >nul 2>&1
git add . >nul 2>&1
git commit -m "部署樂譜庫到 GitHub Pages" >nul 2>&1

:: 取得遠端 URL
cd /d "%PROJECT_DIR%"
for /f "tokens=*" %%i in ('git remote get-url origin 2^>nul') do set "REMOTE_URL=%%i"

if "%REMOTE_URL%"=="" (
    echo     ❌ 找不到 git remote，請先設定 origin
    goto :cleanup
)

:: 推送到 gh-pages 分支
cd /d "%TEMP_DEPLOY%"
git remote add origin "%REMOTE_URL%" >nul 2>&1
git push -f origin gh-pages >nul 2>&1

if %errorlevel% equ 0 (
    echo     ✅ 已推送到 gh-pages 分支
) else (
    echo     ❌ 推送失敗，請檢查網路連線
    goto :cleanup
)

:cleanup
:: 清理臨時目錄
cd /d "%PROJECT_DIR%"
if exist "%TEMP_DEPLOY%" rmdir /s /q "%TEMP_DEPLOY%"

echo.
echo  ════════════════════════════════════════════
echo  ✅ 部署完成！
echo.
echo  📱 手機開啟以下連結即可瀏覽樂譜：
echo.

:: 嘗試解析 GitHub Pages URL
for /f "tokens=4 delims=/:." %%a in ("%REMOTE_URL%") do set "GH_USER=%%a"
echo     https://%GH_USER%.github.io/music-tab-finder/
echo.
echo  💡 提示：GitHub Pages 部署可能需要 1-2 分鐘生效
echo.
pause
