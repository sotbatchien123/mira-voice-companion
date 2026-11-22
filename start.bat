@echo off
chcp 65001 >nul
setlocal
rem Mira - nhap dup de chay. Dong cua so nay la tat Mira.
rem Script co y khong dung nhan goto/call de chay on ca khi file co xuong dong kieu LF.

cd /d "%~dp0"

rem ---- Che do phu: cho server san sang roi mo trinh duyet (chay trong cua so rieng) ----
if /i "%~1"=="--open-browser" (
  set "MIRA_UP="
  for /l %%i in (1,1,60) do (
    if not defined MIRA_UP (
      curl.exe -s -o nul --max-time 2 http://127.0.0.1:8000/api/health && set "MIRA_UP=1" || timeout /t 1 /nobreak >nul
    )
  )
  if defined MIRA_UP (
    start "" http://localhost:8000
  ) else (
    echo [Mira] Server chưa trả lời sau 60 giây. Xem lỗi ở cửa sổ Mira.
    echo [Mira] Khi server chạy xong, tự mở http://localhost:8000
    timeout /t 15 >nul
  )
  exit /b 0
)

echo [Mira] Đang chuẩn bị...

rem ---- 1. Kiem tra uv ----
where uv >nul 2>nul
if errorlevel 1 (
  echo [Mira] Không tìm thấy uv trên máy.
  echo [Mira] Cài uv tại: https://docs.astral.sh/uv/
  echo [Mira] Cài xong thì mở lại start.bat.
  pause
  exit /b 1
)

rem ---- 2. Kiem tra curl ----
set "MIRA_CURL=1"
where curl.exe >nul 2>nul
if errorlevel 1 set "MIRA_CURL="

rem ---- 3. Mira da chay san chua? ----
if defined MIRA_CURL (
  curl.exe -s -o nul --max-time 2 http://127.0.0.1:8000/api/health
  if not errorlevel 1 (
    echo [Mira] Mira đang chạy sẵn rồi, mở trình duyệt thôi.
    start "" http://localhost:8000
    timeout /t 5 >nul
    exit /b 0
  )
)

rem ---- 4. Ollama, bo qua neu dung Claude ----
set "MIRA_SKIP_OLLAMA="
if exist ".env" (
  findstr /i /r /c:"^ *LLM_PROVIDER *= *claude" ".env" >nul 2>nul && set "MIRA_SKIP_OLLAMA=1"
)

if defined MIRA_SKIP_OLLAMA (
  echo [Mira] Đang dùng Claude, bỏ qua Ollama.
)

if not defined MIRA_SKIP_OLLAMA if defined MIRA_CURL (
  set "OLLAMA_UP="
  curl.exe -s -o nul --max-time 2 http://127.0.0.1:11434/api/tags && set "OLLAMA_UP=1"
  if defined OLLAMA_UP (
    echo [Mira] Ollama đã chạy.
  ) else (
    where ollama >nul 2>nul
    if errorlevel 1 (
      echo [Mira] Chưa cài Ollama. Tải tại https://ollama.com rồi chạy: ollama pull qwen3:8b
      echo [Mira] Vẫn mở Mira, trang web sẽ báo lỗi nếu thiếu Ollama.
    ) else (
      echo [Mira] Đang bật Ollama...
      start "Ollama" /min ollama serve
      for /l %%i in (1,1,15) do (
        if not defined OLLAMA_UP (
          timeout /t 1 /nobreak >nul
          curl.exe -s -o nul --max-time 1 http://127.0.0.1:11434/api/tags && set "OLLAMA_UP=1"
        )
      )
      if defined OLLAMA_UP (
        echo [Mira] Ollama đã sẵn sàng.
      ) else (
        echo [Mira] Ollama chưa trả lời sau 15 giây, vẫn chạy tiếp.
      )
    )
  )
)

rem ---- 5. Chay server, mo trinh duyet khi san sang ----
echo [Mira] Đang khởi động server, lần đầu có thể mất khoảng 1 phút...
echo [Mira] Đóng cửa sổ này để tắt Mira.
if defined MIRA_CURL (
  start "Mira - cho mo trinh duyet" /min cmd /c ""%~f0" --open-browser"
) else (
  echo [Mira] Không có curl, server chạy xong thì tự mở http://localhost:8000
)

uv run uvicorn app.main:app --port 8000

echo.
echo [Mira] Server đã dừng.
pause
endlocal
