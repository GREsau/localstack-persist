docker compose build || goto :exit

rmdir /S /Q temp-persisted-data

docker compose run --rm test setup || goto :exit
:: Sanity check...
docker compose run --rm test verify || goto :exit
docker compose stop
:: Ensure changes were persisted...
docker compose run --rm test verify || goto :exit
docker compose stop

rmdir /S /Q temp-persisted-data

:: Ensure changes from previous runs can still be loaded (test backward-compatibility)...
xcopy test-persisted-data temp-persisted-data /E /I
docker compose run --rm test verify || goto :exit
docker compose stop

docker compose down

:exit
@if %errorlevel% neq 0 (
  echo Tests failed with error #%errorlevel%
  exit /b %errorlevel%
) else (
  echo Tests passed!
)
