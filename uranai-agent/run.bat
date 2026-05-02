@echo off
chcp 65001 > nul
echo.
echo =====================================================
echo   霊視師 月詠 - 週間占い記事 自動生成ツール
echo =====================================================
echo.

REM uranai-agentのディレクトリへ移動
cd /d "%~dp0"

REM Pythonとrequirementsの確認
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python が見つかりません
    pause
    exit /b 1
)

REM 依存ライブラリの確認・インストール
pip install anthropic python-dotenv -q

echo.
echo [1] おひつじ座のみテスト生成（動作確認）
echo [2] 全12星座を生成（約10〜15分）
echo [3] 特定の星座だけ生成（英語名を入力）
echo.
set /p choice="選択してください (1/2/3): "

if "%choice%"=="1" (
    python generate_uranai.py --test
) else if "%choice%"=="2" (
    python generate_uranai.py
) else if "%choice%"=="3" (
    set /p sign="星座名を英語で入力 (例: aries, taurus, gemini): "
    python generate_uranai.py --sign %sign%
) else (
    echo 無効な選択です
)

echo.
echo 生成したファイルは output フォルダにあります
echo.
pause
