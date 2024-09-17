REM script to run mypy type checker on this source tree.
pushd .
cd /D "%~dp0"
cd ..\..\
call .\venv\Scripts\activate
set PYTHONPATH=.\src\pywandahydra;%$PYTHONPATH%
python -m mypy ./src/pywandahydra ./unit_test/
popd