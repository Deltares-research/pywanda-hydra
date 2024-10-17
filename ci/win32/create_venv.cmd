rem Short script to initialize virtual environment using venv and pip
rem @echo off
 
pushd .
cd /D "%~dp0"
py -3.10 -m venv ..\..\venv
call ..\..\venv\Scripts\activate.bat
python -m pip install pip-tools
call .\update_dependencies.cmd
call .\install_dependencies.cmd
rem Go to the package directory to call pip install -e .
cd ..\..
py -m pip install -e .
call .\venv\Scripts\deactivate.bat
popd