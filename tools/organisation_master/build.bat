@echo off
rem Builds OrganisationMaster.exe next to this file. Needs Python 3.10+ on PATH.
rem It uses the file code of ../culture_master/culture_master.py and ../country_master/cm_data.py.
cd /d "%~dp0"
rem The newest Python 3 from the py launcher; "python" on PATH can be an older one (3.7 on some PCs,
rem which cannot read ideas.py and builds an exe without it). # Globus
set "PY=python"
where py >nul 2>&1 && py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" || (echo Python 3.10 or newer is needed: install it from python.org. & goto :error)
%PY% -m pip install --quiet --upgrade pyinstaller pillow numpy pygame || goto :error
rem The spec first, then Scripts\slim_spec.py leaves out Tcl files the exe never uses (it starts faster), then the exe.
%PY% -m PyInstaller.utils.cliutils.makespec --onefile --windowed ^
	--name OrganisationMaster ^
	--icon "%~dp0organisation_master.ico" ^
	--add-data "%~dp0organisation_master.ico;." ^
	--exclude-module PIL._avif --exclude-module PIL.AvifImagePlugin ^
	--exclude-module unittest --exclude-module doctest --exclude-module pydoc --exclude-module pydoc_data ^
	--paths "%~dp0Scripts" ^
	--paths "%~dp0..\culture_master" ^
	--paths "%~dp0..\country_master" ^
	--specpath "%~dp0build" ^
	organisation_master.py || goto :error
%PY% "%~dp0Scripts\slim_spec.py" "%~dp0build\OrganisationMaster.spec" || goto :error
%PY% -m PyInstaller --noconfirm --clean --distpath "%~dp0." --workpath "%~dp0build" "%~dp0build\OrganisationMaster.spec" || goto :error
rmdir /s /q "%~dp0build"
echo.
echo Built %~dp0OrganisationMaster.exe
goto :eof

:error
echo Build failed.
exit /b 1
