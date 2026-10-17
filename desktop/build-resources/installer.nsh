; SPDX-License-Identifier: Apache-2.0
; DIST-04 / DIST-09 — what the Windows installer checks before it installs, and
; what the uninstaller asks before it removes anything of the owner's.
;
; Included by electron-builder's NSIS template (electron-builder.yml, nsis.include).
; The installer is per-user and never elevates; nothing here asks for more.

!include "WinVer.nsh"
!include "x64.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "nsDialogs.nsh"

; DIST-05 — the system check runs during installation, before a file is
; copied: the "Checking this computer" page below, after the folder is chosen.
; The floors are the ones `raiker/app/system_check.py` applies when Raiker
; starts, so the installer never accepts a computer the app would refuse.
!define RAIKER_MIN_MEMORY_MB 4096
!define RAIKER_GOOD_MEMORY_MB 8192
!define RAIKER_MIN_DATA_MB 2048
!define RAIKER_GOOD_DATA_MB 20480
; What the installed application itself takes, with room to update in place.
!define RAIKER_MIN_PROGRAM_MB 1024

!ifndef BUILD_UNINSTALLER
Var RaikerBuild
Var RaikerMemoryMB
Var RaikerProgramMB
Var RaikerDataMB
Var RaikerBlocked
Var RaikerCheckDialog

; "16.0 GB" from a size in megabytes.
!macro RaikerGigabytes MB OUT
  IntOp $R8 ${MB} / 1024
  IntOp $R9 ${MB} % 1024
  IntOp $R9 $R9 * 10
  IntOp $R9 $R9 / 1024
  StrCpy ${OUT} "$R8.$R9 GB"
!macroend

Function RaikerMeasure
  ${WinVerGetBuild} $RaikerBuild
  ; Physical memory, from GlobalMemoryStatusEx (MEMORYSTATUSEX is 64 bytes).
  System::Call "*(i 64, i 0, l 0, l 0, l 0, l 0, l 0, l 0, l 0) p .r1"
  System::Call "kernel32::GlobalMemoryStatusEx(p r1) i .r2"
  System::Call "*$1(i, i, l .r3)"
  System::Free $1
  ${If} $2 == 0
    StrCpy $RaikerMemoryMB 0
  ${Else}
    System::Int64Op $3 / 1048576
    Pop $RaikerMemoryMB
  ${EndIf}
  ; Free space where the program goes, and where Raiker keeps its data.
  ; A drive that cannot be measured is unknown, never "no space": an empty
  ; result must not block an install.
  StrCpy $RaikerProgramMB ""
  StrCpy $RaikerDataMB ""
  ${If} $INSTDIR != ""
    ClearErrors
    ${GetRoot} "$INSTDIR" $R0
    ${DriveSpace} "$R0\" "/D=F /S=M" $RaikerProgramMB
    ${If} ${Errors}
      StrCpy $RaikerProgramMB ""
    ${EndIf}
  ${EndIf}
  ClearErrors
  ${GetRoot} "$LOCALAPPDATA" $R0
  ${DriveSpace} "$R0\" "/D=F /S=M" $RaikerDataMB
  ${If} ${Errors}
    StrCpy $RaikerDataMB ""
  ${EndIf}
  StrCpy $RaikerBlocked 0
  ${If} $RaikerMemoryMB != 0
  ${AndIf} $RaikerMemoryMB < ${RAIKER_MIN_MEMORY_MB}
    StrCpy $RaikerBlocked 1
  ${EndIf}
  ${If} $RaikerProgramMB != ""
  ${AndIf} $RaikerProgramMB < ${RAIKER_MIN_PROGRAM_MB}
    StrCpy $RaikerBlocked 1
  ${EndIf}
  ${If} $RaikerDataMB != ""
  ${AndIf} $RaikerDataMB < ${RAIKER_MIN_DATA_MB}
    StrCpy $RaikerBlocked 1
  ${EndIf}
FunctionEnd

; One row: a mark, what was checked, what was found, and what to do about it.
!macro RaikerRow Y MARK TEXT
  ${NSD_CreateLabel} 0 ${Y} 100% 12u "${MARK}   ${TEXT}"
  Pop $R7
!macroend

Function RaikerCheckPage
  Call RaikerMeasure
  !insertmacro MUI_HEADER_TEXT "Checking this computer" "Before anything is installed, Raiker checks that this computer can run it."
  nsDialogs::Create 1018
  Pop $RaikerCheckDialog
  ${If} $RaikerCheckDialog == error
    Abort
  ${EndIf}

  ${If} $RaikerBuild >= 22000
    StrCpy $R1 "Windows 11"
  ${Else}
    StrCpy $R1 "Windows 10"
  ${EndIf}
  !insertmacro RaikerRow 0u "✔" "$R1, build $RaikerBuild, 64-bit"

  ${If} $RaikerMemoryMB == 0
    !insertmacro RaikerRow 16u "·" "Memory could not be measured; Raiker will check it again when it starts"
  ${Else}
    !insertmacro RaikerGigabytes $RaikerMemoryMB $R2
    ${If} $RaikerMemoryMB < ${RAIKER_MIN_MEMORY_MB}
      !insertmacro RaikerRow 16u "✖" "Memory: $R2. Raiker needs at least 4 GB."
    ${ElseIf} $RaikerMemoryMB < ${RAIKER_GOOD_MEMORY_MB}
      !insertmacro RaikerRow 16u "!" "Memory: $R2. Enough for Raiker; local models need 8 GB or more."
    ${Else}
      !insertmacro RaikerRow 16u "✔" "Memory: $R2"
    ${EndIf}
  ${EndIf}

  !insertmacro RaikerGigabytes $RaikerProgramMB $R3
  ${If} $RaikerProgramMB == ""
    !insertmacro RaikerRow 32u "·" "Free space for the program could not be measured"
  ${ElseIf} $RaikerProgramMB < ${RAIKER_MIN_PROGRAM_MB}
    !insertmacro RaikerRow 32u "✖" "Free space for the program: $R3. Free at least 1 GB, or choose another folder."
  ${Else}
    !insertmacro RaikerRow 32u "✔" "Free space for the program: $R3"
  ${EndIf}

  !insertmacro RaikerGigabytes $RaikerDataMB $R4
  ${If} $RaikerDataMB == ""
    !insertmacro RaikerRow 48u "·" "Free space for your data could not be measured; Raiker will check it when it starts"
  ${ElseIf} $RaikerDataMB < ${RAIKER_MIN_DATA_MB}
    !insertmacro RaikerRow 48u "✖" "Free space for your data: $R4. Free at least 2 GB."
  ${ElseIf} $RaikerDataMB < ${RAIKER_GOOD_DATA_MB}
    !insertmacro RaikerRow 48u "!" "Free space for your data: $R4. Enough for Raiker; local models need 20 GB or more."
  ${Else}
    !insertmacro RaikerRow 48u "✔" "Free space for your data: $R4"
  ${EndIf}

  ${If} $RaikerBlocked == 1
    ${NSD_CreateLabel} 0 76u 100% 24u "Raiker can't be installed until the items marked ✖ are fixed. Nothing has been installed."
    Pop $R7
    GetDlgItem $R6 $HWNDPARENT 1
    EnableWindow $R6 0
  ${Else}
    ${NSD_CreateLabel} 0 76u 100% 36u "This computer can run Raiker. When it first opens, Raiker also checks credential protection and the network, and verifies the installation before you create your account."
    Pop $R7
  ${EndIf}
  nsDialogs::Show
FunctionEnd

Function RaikerCheckLeave
  ${If} $RaikerBlocked == 1
    Abort
  ${EndIf}
FunctionEnd
!endif

!macro customPageAfterChangeDir
  Page custom RaikerCheckPage RaikerCheckLeave
!macroend

!macro customInit
  ; Windows 10 1809 (build 17763) is the oldest Windows the frozen host and the
  ; Electron runtime are tested against.
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP|MB_OK "Raiker needs Windows 10 (version 1809) or Windows 11."
    Quit
  ${EndIf}
  ${IfNot} ${AtLeastBuild} 17763
    MessageBox MB_ICONSTOP|MB_OK "Raiker needs Windows 10 version 1809 or newer. Update Windows, then run this installer again."
    Quit
  ${EndIf}
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP|MB_OK "Raiker needs a 64-bit edition of Windows."
    Quit
  ${EndIf}
  ; A silent install shows no pages, so it applies the same floors here and
  ; exits with code 2 instead of installing on a computer that cannot run it.
  ${If} ${Silent}
    Call RaikerMeasure
    ${If} $RaikerBlocked == 1
      SetErrorLevel 2
      Quit
    ${EndIf}
  ${EndIf}
!macroend

!macro customUnInstall
  ; An update runs the previous version's uninstaller with --updated. It must
  ; never touch the owner's data, and it must not ask.
  ${IfNot} ${isUpdated}
    ; Stop a running host and remove its background registration first, through
    ; the same plan `raiker-app uninstall` states (raiker/app/uninstall.py).
    ; Silent uninstalls keep data: removing it is a choice someone makes, never
    ; a default.
    StrCpy $0 "keep"
    ${IfNot} ${Silent}
      MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 \
        "Also remove your Raiker data from this computer?$\r$\n$\r$\nThis erases your conversations, memory, settings and saved provider keys in $LOCALAPPDATA\Raiker. It cannot be undone.$\r$\n$\r$\nChoose No to keep them, for example to reinstall later. Models you installed with other tools, such as Ollama, are never removed." \
        /SD IDNO IDNO raiker_keep_data
      StrCpy $0 "erase"
      raiker_keep_data:
    ${EndIf}
    IfFileExists "$INSTDIR\resources\host\Raiker.exe" 0 raiker_no_host
      nsExec::ExecToLog '"$INSTDIR\resources\host\Raiker.exe" quit --force'
      Pop $1
      nsExec::ExecToLog '"$INSTDIR\resources\host\Raiker.exe" uninstall --data $0 --yes'
      Pop $1
    raiker_no_host:
  ${EndIf}
!macroend
