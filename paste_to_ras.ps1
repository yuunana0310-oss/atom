$inbox = "C:\Users\yuuna\agens\RAS_IMPORT_BOX"
$importer = "C:\Users\yuuna\agens\knowledge\import_research.py"

Write-Host "--- RAS Import (English Message Mode) ---"

# Use English only to avoid encoding errors
$content = Get-Clipboard -Raw

if (-not $content) { 
    Write-Host "Error: Clipboard is empty!"
} else {
    $path = Join-Path $inbox "clipboard_import.md"
    Set-Content -Path $path -Value $content -Encoding UTF8
    Write-Host "1. Saved clipboard successfully."
    
    Write-Host "2. Starting Python import script..."
    # Choose python or py
    $py_cmd = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "py" }
    & $py_cmd $importer
    
    Write-Host "3. Finished. Your asset has been stored in RAS."
}

Write-Host "Press [Enter] to Close this window."
Read-Host
