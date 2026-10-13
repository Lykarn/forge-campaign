@echo off
rem Gate B helper: start a duel against any Adventure enemy, by name, without walking to it.
rem Copy this file into a SEPARATE unzipped ForgeCampaign folder (not the one with your saves):
rem it makes a throwaway Adventure world for the fight. Then double-click it.
rem It uses Neo Forge's own Adventure self-test (selftest=anteduel), with you playing the duel.

cd /d "%~dp0"
if not exist "ForgeCampaign.exe" (
    echo Put this file inside the ForgeCampaign folder, next to ForgeCampaign.exe.
    pause
    exit /b 1
)
echo Examples: Goblin (Grunt), Storm Titan (Elite), Jace, Sliver Queen, Lathliss (Bosses)
set /p ENEMY=Enemy to fight:
if "%ENEMY%"=="" set ENEMY=Jace
set JAVA_TOOL_OPTIONS=-Dneo.adventure.autoLaunch=true -Dneo.adventure.selftest=anteduel -Dneo.adventure.ante=false "-Dneo.adventure.enemy=%ENEMY%" -Dneo.adventure.snapshotMs=3600000
start "" "ForgeCampaign.exe"
