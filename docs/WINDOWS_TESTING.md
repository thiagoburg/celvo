# Windows 11 manual validation checklist

Run this checklist on a clean Windows 11 machine after installing a Celvo build and its whisper.cpp runtime. Record Celvo version, Windows build, Python version, CPU, RAM, audio devices, and driver versions with the results. Automated CI is hardware-free and does not count as completing these physical tests.

For each row, record **Actual result**, **date**, **device/driver**, and a link to any diagnostic log. Use `Not run` until the procedure has actually been performed.

| # | Test | Expected behavior | Actual result |
|---:|---|---|---|
| 1 | Fresh Windows 11 x64 install | Installer completes, verifies executable/model, and `celvo diagnose` passes. | Not run |
| 2 | Install as a standard user without elevation | No administrator prompt; user PATH and user data directories are configured. | Not run |
| 3 | Microphone-only recording | Selected microphone produces a valid non-empty WAV; stop and reopen it successfully. | Not run |
| 4 | Default system loopback recording | Default Windows playback output is captured through WASAPI and saved as WAV. | Not run |
| 5 | Simultaneous microphone and system recording | Both signals appear in the final mix with the expected relative timing. | Not run |
| 6 | 30-second recording | Final duration and WAV header are correct; processing starts normally. | Not run |
| 7 | 30-minute recording | No reported overflows, unexplained gaps, growing memory use, or synchronization drift. | Not run |
| 8 | Two-hour recording | Recording finalizes, remains playable, and has no noticeable drift or corrupted frames. | Not run |
| 9 | Bluetooth headphone output | Selected Bluetooth loopback endpoint records playback; document profile/rate/channel limitations. | Not run |
| 10 | USB microphone | Explicit device selection works and recorded audio is intelligible. | Not run |
| 11 | Disconnect a selected device while recording | Recording fails clearly, stops promptly, does not claim success, and retains partial source files. | Not run |
| 12 | Ctrl+C during a healthy recording | Streams close cleanly and the WAV is finalized if valid; no orphaned capture process remains. | Not run |
| 13 | Process a completed recording | Offline whisper.cpp exits successfully and writes a UTF-8 transcription. | Not run |
| 14 | Process an interrupted/partial capture | Invalid/incomplete input is rejected clearly; it is never presented as a complete recording. | Not run |
| 15 | Restart after an audio error | Celvo can be started again and enumerate devices without stale streams/processes. | Not run |
| 16 | Disable internet after installation | Recording and transcription still work without network access. | Not run |
| 17 | Install and run from paths containing spaces | Install, model, executable, audio, and transcription paths resolve correctly. | Not run |
| 18 | Update with existing recordings | Application update leaves all prior recordings and transcripts intact and discoverable. | Not run |

## Desktop UI check

| Test | Expected behavior | Actual result |
|---|---|---|
| Launch Celvo from Start menu or `celvo ui` | The Celvo window opens, lists recordings and devices, and leaves the terminal commands available. | Not run |
| Record and stop from the window | The timer advances, Stop finalizes a WAV, and the recording appears in the library. Capture errors are shown and never appear as a successful recording. | Not run |
| Transcribe a selected recording | The window stays responsive, reports success or failure, and enables opening the transcript after success. | Not run |

## Automated CI coverage

GitHub Actions runs Python compilation, import checks, pytest, and Ruff on Ubuntu and `windows-latest` with Python 3.10–3.13. The Windows whisper.cpp workflow builds the pinned v1.9.5 CLI in Release mode and runs its help/version smoke checks. These jobs verify mocked capture, WAV/mixer behavior, file discovery, command handling, and packaged-runtime construction. They do not access microphones or WASAPI devices, and synthetic large-track tests do not prove two-hour hardware reliability.
