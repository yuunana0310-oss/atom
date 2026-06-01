@echo off
chcp 65001 > nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$env:MVG_SCRIPT_PATH = (Join-Path '%~dp0' 'new-memo.ps1'); $code = Get-Content -LiteralPath $env:MVG_SCRIPT_PATH -Raw -Encoding UTF8; $block = [ScriptBlock]::Create($code); & $block %*"
