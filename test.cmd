docker-compose build || goto :exit

rmdir /S /Q .\temp-persisted-data

docker-compose up -d localstack-compere
docker-compose run --rm test setup || goto :exit
docker-compose restart localstack-compere
docker-compose run --rm test verify || goto :exit
docker-compose down

rmdir /S /Q .\temp-persisted-data

xcopy persisted-data temp-persisted-data /E /I

docker-compose up -d localstack-compere
docker-compose run --rm test verify || goto :exit
docker-compose down

:exit
@if %errorlevel% neq 0 echo Failed with error #%errorlevel%
exit /b %errorlevel%