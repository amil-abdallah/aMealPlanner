@echo off

if "%1"=="backend" npx repomix --config .repomix/backend.json 
if "%1"=="frontend" npx repomix --config .repomix/frontend.json 
if "%1"=="full" npx repomix --config .repomix/full.json --compress

if "%1"=="" echo Usage: ctx [backend^|frontend^|full]