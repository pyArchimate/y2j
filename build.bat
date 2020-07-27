cd %~dp0
rem venv\scripts\activate
pip install -r requirements.txt
pyinstaller -F y2j.spec && copy /y dist\y2j.exe %appdata%\..\local\Programs