@echo off
setlocal
cd /d "%~dp0"
echo ================================================================
echo   TikTokFashionTrend - Don dep lich su Git va push len GitHub
echo   Repo: https://github.com/VanHau2508/TikTokFashionTrend
echo ================================================================
echo.
echo   CANH BAO: Script nay se TAO LAI lich su commit (reset sach)
echo   va FORCE-PUSH de len GitHub. Lich su commit cu se bi thay the.
echo   Mot nhanh backup "backup-old-main" duoc giu lai tren may ban.
echo.
set /p OK="Go 'y' de tiep tuc, phim khac de huy: "
if /i not "%OK%"=="y" ( echo Da huy. & pause & exit /b 0 )
echo.

echo [0/5] Kiem tra day co phai repo git khong...
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 ( echo LOI: Thu muc nay khong phai repo git. & pause & exit /b 1 )

echo [1/5] Tao nhanh backup an toan "backup-old-main"...
git branch -f backup-old-main HEAD

echo [2/5] Tao lich su moi (orphan, khong dinh commit cu)...
git checkout --orphan __clean_tmp__
if errorlevel 1 ( echo LOI khi tao orphan branch. & pause & exit /b 1 )

echo [3/5] Xoa index cu de .gitignore co hieu luc voi MOI file...
git rm -r --cached . >nul 2>&1
echo       Them lai file (ton trong .gitignore) va tao commit sach...
git add -A
git commit -m "Clean source-only version. Setup: pip install -r requirements.txt, npm install trong frontend, playwright install"
if errorlevel 1 ( echo LOI khi commit. & pause & exit /b 1 )

echo [4/5] Doi ten nhanh moi thanh main...
git branch -M main

echo [5/5] Force-push len GitHub (origin main)...
git push -f origin main
if errorlevel 1 (
  echo.
  echo LOI khi push - thuong do chua dang nhap GitHub tren may.
  echo Hay dang nhap Git/GitHub roi chay lai script nay.
  pause
  exit /b 1
)

echo.
echo ===================== HOAN TAT =====================
echo  Repo tren GitHub gio chi con ma nguon sach.
echo  Nhanh "backup-old-main" van con TREN MAY BAN (an toan).
echo.
echo  Sau khi vao GitHub kiem tra thay OK, chay tiep
echo  "shrink_local_git.bat" de thu nho thu muc .git tren may.
echo ===================================================
pause
