; ---------------------------------------------------------------------------
; Jianpu Converter -- NSIS installer script
; Build:  makensis.exe JianpuConverter.nsi
; Produces: ..\release\JianpuConverter-Setup-<version>.exe
; Per-user install (no administrator rights required).
;
; Silent self-update contract (used by jianpu_converter/updater.py):
;     JianpuConverter-Setup-1.0.1.exe /S /RELAUNCH
;   /S        run without any dialog (NSIS built-in switch)
;   /RELAUNCH start the freshly installed app again when finished
; The installer closes a running copy, removes the previous files (only when
; our own uninstall entry points at the target folder) and re-creates the
; shortcuts and registry entries.
; ---------------------------------------------------------------------------

Unicode true

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

; ---------------------------------- Metadata ---------------------------------
!define APP_NAME      "Jianpu Converter"
!define APP_SHORTNAME "JianpuConverter"
!define APP_VERSION   "1.0.1"
!define APP_PUBLISHER "Jianpu"
!define APP_EXE       "JianpuConverter.exe"
!define APP_REGKEY    "Software\Microsoft\Windows\CurrentVersion\Uninstall\JianpuConverter"
!define APP_EXTKEY    "JianpuConverter.musicxml"

; Version resource so Explorer -> Properties -> Details on the *setup* file
; shows which release it is (NSIS wants four numbers for VIProductVersion).
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName"     "${APP_NAME}"
VIAddVersionKey "FileDescription" "${APP_NAME} Setup"
VIAddVersionKey "FileVersion"     "${APP_VERSION}"
VIAddVersionKey "ProductVersion"  "${APP_VERSION}"
VIAddVersionKey "LegalCopyright"  "${APP_PUBLISHER}"

; ---------------------------------- Icons ------------------------------------
Icon "..\assets\app.ico"
UninstallIcon "..\assets\app.ico"

; ------------------------------- Installer options ---------------------------
Name "${APP_NAME}"
Caption "${APP_NAME} ${APP_VERSION} Setup"
OutFile "..\release\JianpuConverter-Setup-${APP_VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\${APP_SHORTNAME}"
RequestExecutionLevel user
SetCompressor /SOLID lzma
CRCCheck on

; ------------------------------ MUI configuration ----------------------------
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${APP_NAME}"
!define MUI_FINISHPAGE_LINK "MusicXML to Jianpu (简谱) PDF Converter"
!define MUI_FINISHPAGE_LINK_LOCATION "https://ssb22.user.srcf.net/mwrhome/jianpu-ly.html"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ------------------------------- Install section ----------------------------
Section "Install"
    ; --- Upgrade helpers ----------------------------------------------------
    ; Close a running copy so its files are not locked while we replace them.
    ; The auto-updater makes the app exit first, so this mainly helps when a
    ; friend double-clicks the new setup while the old version is still open.
    nsExec::Exec '"$SYSDIR\taskkill.exe" /IM "${APP_EXE}"'
    Pop $0
    Sleep 600
    nsExec::Exec '"$SYSDIR\taskkill.exe" /IM "${APP_EXE}" /F'
    Pop $0
    Sleep 300

    ; Remove the previous version's files so modules that were renamed or
    ; dropped do not linger.  Only done when OUR uninstall entry points at
    ; $INSTDIR, so a custom folder picked by the user is never wiped.
    ReadRegStr $0 HKCU "${APP_REGKEY}" "InstallLocation"
    ${If} $0 == "$INSTDIR"
        RMDir /r "$INSTDIR"
    ${EndIf}

    SetOutPath "$INSTDIR"

    ; The whole application folder: exe, bundled Python runtime, and the
    ; portable LilyPond engine (found automatically next to the exe).
    File /r "..\dist\${APP_SHORTNAME}\*.*"

    ; Start Menu shortcut
    CreateDirectory "$SMPROGRAMS\${APP_SHORTNAME}"
    CreateShortcut "$SMPROGRAMS\${APP_SHORTNAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
    ; Desktop shortcut
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"

    ; Uninstaller + Add/Remove Programs entry
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    WriteRegStr  HKCU "${APP_REGKEY}" "DisplayName"     "${APP_NAME}"
    WriteRegStr  HKCU "${APP_REGKEY}" "DisplayVersion"  "${APP_VERSION}"
    WriteRegStr  HKCU "${APP_REGKEY}" "Publisher"       "${APP_PUBLISHER}"
    WriteRegStr  HKCU "${APP_REGKEY}" "DisplayIcon"     "$INSTDIR\${APP_EXE}"
    WriteRegStr  HKCU "${APP_REGKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr  HKCU "${APP_REGKEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
    WriteRegStr  HKCU "${APP_REGKEY}" "InstallLocation" "$INSTDIR"
    WriteRegDWORD HKCU "${APP_REGKEY}" "NoModify"       1
    WriteRegDWORD HKCU "${APP_REGKEY}" "NoRepair"       1
    WriteRegDWORD HKCU "${APP_REGKEY}" "EstimatedSize"  153000

    ; .musicxml file association (open with this app by double-click)
    WriteRegStr HKCU "Software\Classes\.musicxml" "" "${APP_EXTKEY}"
    WriteRegStr HKCU "Software\Classes\${APP_EXTKEY}" "" "${APP_NAME} MusicXML File"
    WriteRegStr HKCU "Software\Classes\${APP_EXTKEY}\DefaultIcon" "" "$INSTDIR\${APP_EXE},0"
    WriteRegStr HKCU "Software\Classes\${APP_EXTKEY}\shell\open\command" "" '"$INSTDIR\${APP_EXE}" "%1"'

    ; Refresh the shell so the new file association takes effect
    System::Call "shell32.dll::SHChangeNotify(i, i, i, i) v (0x08000000, 0, 0, 0)"

    ; Silent self-update: the app passes /RELAUNCH so the user is back in the
    ; new version right after the upgrade, with nothing else to click.
    ${GetParameters} $R0
    ClearErrors
    ${GetOptions} $R0 "/RELAUNCH" $R1
    ${IfNot} ${Errors}
        Exec '"$INSTDIR\${APP_EXE}"'
    ${EndIf}
SectionEnd

; ------------------------------ Uninstall section ----------------------------
Section "Uninstall"
    ; Remove shortcuts
    Delete "$SMPROGRAMS\${APP_SHORTNAME}\${APP_NAME}.lnk"
    RMDir  "$SMPROGRAMS\${APP_SHORTNAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"

    ; Remove file association, but only if we still own it
    ReadRegStr $0 HKCU "Software\Classes\.musicxml" ""
    ${If} $0 == "${APP_EXTKEY}"
        DeleteRegKey HKCU "Software\Classes\.musicxml"
    ${EndIf}
    DeleteRegKey HKCU "Software\Classes\${APP_EXTKEY}"

    ; Remove the Add/Remove Programs entry
    DeleteRegKey HKCU "${APP_REGKEY}"

    ; Remove the application itself
    RMDir /r "$INSTDIR"
SectionEnd
