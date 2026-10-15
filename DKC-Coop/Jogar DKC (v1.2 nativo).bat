@echo off
rem Port nativo de Donkey Kong Country (USA v1.2) - DKC-Coop, fase 2.
rem Widescreen desligado: os ajustes de widescreen do port ainda sao especificos da v1.0.
set DKC1_WIDESCREEN=0
start "" "%~dp0DKC1Recomp\build\dkc1_v12_desktop.exe" "%~dp0rom\dkc1_v12.sfc"
