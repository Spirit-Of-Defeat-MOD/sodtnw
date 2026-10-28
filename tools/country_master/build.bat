@echo off
rem Builds CountryMaster.exe next to this file. Needs Python 3.10+ on PATH.
rem It uses the file and map code of ../culture_master/culture_master.py.
cd /d "%~dp0"
rem The newest Python 3 from the py launcher; "python" on PATH can be an older one (3.7 on some PCs). # Globus
set "PY=python"
where py >nul 2>&1 && py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" || (echo Python 3.10 or newer is needed: install it from python.org. & goto :error)
%PY% -m pip install --quiet --upgrade pyinstaller pillow numpy || goto :error
rem The spec first, then slim_spec.py leaves out Tcl files the exe never uses (it starts faster), then the exe.
%PY% -m PyInstaller.utils.cliutils.makespec --onefile --windowed ^
	--name CountryMaster ^
	--icon "%~dp0country_master.ico" ^
	--add-data "%~dp0country_master.ico;." ^
	--paths "%~dp0..\culture_master" ^
	--paths "%~dp0..\organisation_master" ^
	--paths "%~dp0..\organisation_master\Scripts" ^
	--specpath "%~dp0build" ^
	country_master.py || goto :error
%PY% "%~dp0..\organisation_master\Scripts\slim_spec.py" "%~dp0build\CountryMaster.spec" || goto :error
%PY% -m PyInstaller --noconfirm --clean --distpath "%~dp0." --workpath "%~dp0build" "%~dp0build\CountryMaster.spec" || goto :error
rmdir /s /q "%~dp0build"
echo.
echo Built %~dp0CountryMaster.exe
goto :eof

:error
echo Build failed.
exit /b 1
