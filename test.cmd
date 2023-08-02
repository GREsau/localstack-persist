docker-compose build || goto :exit

rmdir /S /Q .\temp-persisted-data

docker-compose run --rm test setup || goto :exit
docker-compose run --rm test verify || goto :exit
docker-compose down
docker-compose run --rm test verify || goto :exit
docker-compose down

rmdir /S /Q .\temp-persisted-data

xcopy persisted-data temp-persisted-data /E /I

docker-compose up -d localstack-compere
docker-compose run --rm test verify || goto :exit

:exit
docker-compose down
@if %errorlevel% neq 0 echo Failed with error #%errorlevel%
exit /b %errorlevel%