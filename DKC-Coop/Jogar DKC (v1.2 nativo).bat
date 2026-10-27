@echo off
rem Port nativo de Donkey Kong Country (USA v1.2) - DKC-Coop.
rem Widescreen desligado: os ajustes de widescreen do port ainda sao especificos da v1.0.
set DKC1_WIDESCREEN=0
rem Gravador de reproducao: F9 salva as ultimas entradas e estados em "repro" (para diagnostico).
set DKC1_FLIGHT_RECORDER=1
set DKC1_FLIGHT_RECORDER_DIR=%~dp0repro
if not exist "%~dp0repro" mkdir "%~dp0repro"
start "" "%~dp0DKC1Recomp\build\dkc1_v12_desktop.exe" "%~dp0rom\dkc1_v12.sfc"
