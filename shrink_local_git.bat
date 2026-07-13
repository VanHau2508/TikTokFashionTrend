@echo off
setlocal
cd /d "%~dp0"
echo ================================================================
echo   Thu nho thu muc .git tren may (xoa du lieu cu, KHONG hoan tac)
echo ================================================================
echo   Chi chay sau khi da kiem tra GitHub OK!
echo.
set /p OK="Go 'y' de tiep tuc: "
if /i not "%OK%"=="y" ( echo Da huy. & pause & exit /b 0 )

echo Xoa nhanh backup...
git branch -D backup-old-main 2>nul
echo Don dep reflog va nen lai .git...
git remote prune origin
git reflog expire --expire=now --all
git gc --prune=now --aggressive
echo.
echo Xong. Kiem tra lai dung luong thu muc .git (le ra chi con vai MB).
pause
