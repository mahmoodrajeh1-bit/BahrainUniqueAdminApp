@echo off
set /p NAME=Enter this computer's display name:
powershell -NoProfile -Command "$p='remote_config.json'; if(Test-Path $p){$j=Get-Content $p -Raw|ConvertFrom-Json}else{$j=[pscustomobject]@{computer_name=$env:COMPUTERNAME;port=8765;token=''}}; $j.computer_name='%NAME%'; $j|ConvertTo-Json|Set-Content $p -Encoding UTF8"
echo Computer name saved. Restart PriceMatcherRemote.exe.
pause
