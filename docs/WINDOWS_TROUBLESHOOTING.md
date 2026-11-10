# Windows 11 troubleshooting

Start with:

```powershell
celvo diagnose
celvo devices
```

## Python is missing or unsupported

Install 64-bit CPython 3.10, 3.11, 3.12, or 3.13 and enable the Python launcher (`py`). Reopen PowerShell and check `py -0p`. The installer does not require administrator privileges when Python is installed for the current user.

## `whisper-cli.exe` is missing

The installer verifies the official pinned x64 runtime archive. If the upstream archive cannot be reached, build the pinned whisper.cpp runtime as a developer:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -BuildWhisper
```

The source build requires CMake and Visual Studio C++ build tools. You can also set `CELVO_WHISPER_CLI` to the full path of an existing `whisper-cli.exe`.

## The model is missing or fails verification

The installer stores the full-precision `ggml-large-v3.bin` under `%USERPROFILE%\Documents\Celvo\models`. It verifies the file's SHA-256 before making it available. The file is about 3.1 GB and requires substantial free disk space and memory. If the download was interrupted, rerun the installer. Older installations with only `ggml-large-v3-q5_0.bin` continue to work as a lower-storage fallback. For a manually installed model, set `CELVO_WHISPER_MODEL` to its full path and run `celvo diagnose` again.

## Microphone permission or device errors

In Windows Settings, open **Privacy & security → Microphone** and allow microphone access for desktop apps. Close applications that may exclusively hold the device, reconnect it, then run `celvo devices`. Select the listed microphone with `--microphone-device`. Celvo reports unsupported formats and disconnected streams instead of switching devices silently.

## Windows output selection and WASAPI errors

Select the playback output shown as a `system` device in `celvo devices`:

```powershell
celvo record --system-device 4
```

WASAPI loopback needs an output endpoint that Windows exposes through WASAPI. If capture cannot open it, confirm the device is enabled in Windows Sound settings, set it as the default output or select it explicitly, then restart Celvo. No PulseAudio utilities are used by the native Windows backend.

Some WASAPI loopback devices stop delivering callbacks while nothing is playing. Celvo now treats that as silence and writes zero-valued samples for the quiet interval, then places later callback audio at its timestamp. A quiet system-audio recording is therefore valid silence rather than a five-second stall error. If Windows reports the stream inactive or reports an overflow, Celvo still fails the recording and preserves its partial capture.

## Bluetooth limitations

Bluetooth headsets can switch between high-quality stereo output and a hands-free communications profile when the microphone is active. The active endpoint may change its rate, channels, or device ID. Select the current endpoint after the profile switch. If a specific headset profile cannot be captured, use a USB or built-in microphone and document the device, driver, and Windows build in a bug report.

## Synchronization or missing audio

`celvo record` aligns microphone and loopback tracks using monotonic capture times and measures their sample counts. Driver timestamps and independent hardware clocks still affect real-world alignment. On a long meeting, note the elapsed duration and compare a clear shared sound at the start and end. If Celvo reports overflow or a disconnected/stopped source, it exits with an error and preserves partial files in `%USERPROFILE%\Documents\Celvo\temporary`.

### A console window appears during transcription

The Celvo desktop app launches whisper.cpp without creating a Windows console window. Update Celvo with the current installer if an older installed version still opens a terminal. Transcription output remains local and the app shows a completion notification when the text file is ready.

## Installation failure

Rerun the installer after fixing the reported cause. Model and runtime files are downloaded to temporary files, checked, and only then moved into place. Installed versions are retained side by side; recordings and transcripts live outside the application install directory. If the pinned upstream runtime archive is unavailable, use the developer source-build option above.

## Offline use

After the installer has verified the Python packages, whisper.cpp runtime, and model, disable the network and run `celvo record` followed by `celvo process`. Celvo itself makes no network requests during capture or transcription.
