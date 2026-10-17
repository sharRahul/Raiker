; SPDX-License-Identifier: Apache-2.0
; DIST-04 / DIST-09 — what the Windows installer checks before it installs, and
; what the uninstaller asks before it removes anything of the owner's.
;
; Included by electron-builder's NSIS template (electron-builder.yml, nsis.include).
; The installer is per-user and never elevates; nothing here asks for more.

!include "WinVer.nsh"
!include "x64.nsh"

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
