@echo off
rem Builds TemplateMaster.exe next to this file (change the name and script below for your master). Needs Python 3.10+.
cd /d "%~dp0"
set "PY=python"
where py >nul 2>&1 && set "PY=py -3"
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" || (echo Python 3.10 or newer is needed: install it from python.org. & goto :error)
%PY% -m pip install --quiet --upgrade pyinstaller pillow numpy pygame || goto :error
rem The spec first, then slim_spec.py leaves out Tcl files the exe never uses (it starts faster), then the exe.
%PY% -m PyInstaller.utils.cliutils.makespec --onefile --windowed ^
	--name TemplateMaster ^
	--paths "%~dp0..\organisation_master\Scripts" ^
	--paths "%~dp0..\culture_master" ^
	--exclude-module PIL._avif --exclude-module PIL.AvifImagePlugin ^
	--exclude-module unittest --exclude-module doctest --exclude-module pydoc --exclude-module pydoc_data ^
	--specpath "%~dp0build" ^
	template_master.py || goto :error
%PY% "%~dp0..\organisation_master\Scripts\slim_spec.py" "%~dp0build\TemplateMaster.spec" || goto :error
%PY% -m PyInstaller --noconfirm --clean --distpath "%~dp0." --workpath "%~dp0build" "%~dp0build\TemplateMaster.spec" || goto :error
rmdir /s /q "%~dp0build"
echo.
echo Built %~dp0TemplateMaster.exe
goto :eof

:error
echo Build failed.
exit /b 1
