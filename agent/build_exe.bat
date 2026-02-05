@echo off
echo Installing dependencies...
pip install -r requirements.txt

echo Building AlaskaAgent.exe...
pyinstaller --noconsole --onefile --name AlaskaAgent --add-data ".env;." src/main.py

echo.
echo Build Complete!
echo Your app is located in: dist\AlaskaAgent.exe
echo.
pause
