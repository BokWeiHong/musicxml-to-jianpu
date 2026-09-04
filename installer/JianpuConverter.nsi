; ---------------------------------------------------------------------------
; Jianpu Converter -- NSIS installer script
; Build:  makensis.exe JianpuConverter.nsi
; Produces: ..\release\JianpuConverter-Setup.exe
; Per-user install (no administrator rights required).
; ---------------------------------------------------------------------------

Unicode true

!include "MUI2.nsh"
!include "LogicLib.nsh"

; ---------------------------------- Metadata ---------------------------------
!define APP_NAME      "Jianpu Converter"
!define APP_SHORTNAME "JianpuConverter"
!define APP_VERSION   "1.0.0"
!define APP_PUBLISHER "Jianpu"
!define APP_EXE       "JianpuConverter.exe"
!define APP_REGKEY    "Software\Microsoft\Windows\CurrentVersion\Uninstall\JianpuConverter"
!define APP_EXTKEY    "JianpuConverter.musicxml"

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
