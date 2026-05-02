$Action = New-ScheduledTaskAction -Execute "python.exe" -Argument "c:\Users\yuuna\agens\knowledge\ai_tech\fetch_ai_news.py" -WorkingDirectory "c:\Users\yuuna\agens\knowledge\ai_tech"
$Trigger = New-ScheduledTaskTrigger -Daily -At 7:00AM
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$Task = New-ScheduledTask -Action $Action -Trigger $Trigger -Settings $Settings
Register-ScheduledTask -TaskName "RAG_AI_News_Updater" -InputObject $Task -Force
Write-Host "[SUCCESS] Task Scheduler Initialized Successfully."
