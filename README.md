# Celvo

![Linux](https://img.shields.io/badge/Linux-supported-black?logo=linux)
![Windows](https://img.shields.io/badge/Windows%2011-automated%20CI%20%7C%20hardware%20validation%20pending-blue?logo=windows)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/github/license/thiagoburg/celvo)

Celvo is a local-first command line recorder and transcription tool. It captures microphone and system output audio, saves WAV recordings on your computer, and transcribes them offline with whisper.cpp. Recordings and transcripts are never uploaded.

Windows 11 support uses microphone input through PortAudio and system output capture through WASAPI loopback. Linux retains PulseAudio-compatible capture. Automated Windows tests do not replace the physical-device checks in [the Windows validation checklist](docs/WINDOWS_TESTING.md); Windows hardware validation is pending.

## Requirements

- Windows 11 x64, or a supported Linux desktop with PulseAudio or PipeWire's PulseAudio compatibility service.
- Python 3.10–3.13 for the tested installer and CI matrix. Celvo's package requires Python 3.10 or newer.
- About 8 GB free disk space during initial setup, including the 3.1 GB full-precision Large-v3 model and build/download staging files.
- Internet access for setup and model download only. Recording and transcription run locally and work offline after installation.

Celvo defaults to the full-precision multilingual Whisper Large-v3 model for transcription quality. It needs roughly 3.1 GB of disk space and substantial memory; whisper.cpp loads it only while transcribing. Existing Q5_0 installations remain usable as a compatibility fallback until the full model is installed.

## Windows 11 installation

Clone the project and run the installer from PowerShell as your normal user:

```powershell
git clone https://github.com/thiagoburg/celvo.git
cd celvo
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer creates a versioned virtual environment under `%LOCALAPPDATA%\Programs\Celvo`, keeps application versions side by side, and stores recordings, transcripts, temporary files, and the model under `%USERPROFILE%\Documents\Celvo`. It does not require administrator privileges. A new terminal may be needed after installation so the user PATH update is visible.

The installer downloads the official whisper.cpp Windows x64 archive for the pinned v1.9.5 source revision and verifies its SHA-256 digest. Developers with CMake and Visual Studio C++ build tools can instead build locally:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -BuildWhisper
```

Verify the installation:

```powershell
celvo --version
celvo diagnose
celvo devices
```

For device permissions, output selection, Bluetooth notes, and recovery steps, see [Windows troubleshooting](docs/WINDOWS_TROUBLESHOOTING.md).

## Linux installation

On Fedora, Ubuntu/Debian, Arch, or openSUSE, run the installer:

```bash
curl -fsSL https://raw.githubusercontent.com/thiagoburg/celvo/main/install.sh | bash
```

The installer uses the system package manager for Python, PortAudio, PulseAudio utilities, CMake, and a C++ compiler. It builds whisper.cpp at the pinned `v1.9.5` tag and verifies the downloaded model checksum. Linux system audio requires a PulseAudio monitor source; PipeWire desktops should provide the PulseAudio compatibility layer. Existing installations are retained as timestamped backups until replacement verification succeeds.

If the installer was run from a checkout instead:

```bash
bash ./setup.sh
```

Ensure `~/.local/bin` is on `PATH`. The installer provides `celvo`, plus the compatible `record` and `process` shortcuts.

## WSL2 (optional)

Install Celvo inside a supported WSL2 Linux distribution using the Linux instructions above. WSL2 uses the Linux/PulseAudio backend. Device visibility depends on the WSL audio integration and host configuration; native Windows WASAPI loopback is available only when running the Windows build. WSL2 audio devices and synchronization need separate hardware validation. The Tkinter UI can open in a WSLg desktop session when Tk and GUI forwarding are available, but that setup has not been hardware-validated.

## Recording and transcription

For everyday desktop use, launch **Celvo** from the Windows Start menu or your Linux applications menu. The compact, dark-only interface records both the default microphone and default system output; start and stop the recording, then select a recording in the library to transcribe, open, rename, or move to the Recycle Bin/desktop trash. Renaming also renames the matching transcript. Deletion asks for confirmation and uses the operating system's recoverable trash. A visual and audible notification appears when transcription finishes. Audio and transcripts remain on your computer.

You can also open the window from a terminal with `celvo ui`. The desktop UI uses Tkinter/ttk and does not add a Python GUI framework dependency. Linux installations need the distribution's Tk package; the installer installs it on supported distributions.

By default Celvo records microphone and system audio together. The terminal workflow remains available:

```text
celvo record
celvo process
```

Choose a source explicitly when needed:

```text
celvo record --source microphone
celvo record --source system
celvo record --source both
```

List available devices and select one by the ID displayed:

```text
celvo devices
celvo record --microphone-device 2 --system-device 5
```

Use `celvo --help` and `celvo record --help` for all options. `celvo diagnose` checks writable directories, audio-device enumeration, the whisper.cpp executable, and the model. A requested source that is unavailable fails with an error instead of switching capture modes.

`Ctrl+C` stops capture and finalizes a valid WAV if all sources stop cleanly. A failed or stalled source returns a nonzero exit code and preserves partial per-source WAVs under the temporary recording directory for recovery. It does not report the failed recording as complete.

## Data locations and configuration

Linux and Windows keep recordings and transcriptions under the user's Documents folder: `~/Documents/celvo/audio` and `~/Documents/celvo/transcription` on Linux, and `%USERPROFILE%\Documents\Celvo\audio` and `%USERPROFILE%\Documents\Celvo\transcription` on Windows. The data root also contains `temporary` and `models` subdirectories. Application code and whisper.cpp are installed separately from this data. Uninstalling or updating Celvo does not remove user recordings.

Override paths with environment variables:

| Variable | Purpose |
| --- | --- |
| `CELVO_DATA_DIR` | Base user data directory |
| `CELVO_AUDIO_DIR` | Recordings directory |
| `CELVO_TRANSCRIPTIONS_DIR` | Transcriptions directory |
| `CELVO_TEMP_DIR` | Temporary and recoverable partial captures |
| `CELVO_MODEL_DIR` | Whisper model directory |
| `CELVO_WHISPER_CLI` | Full path to `whisper-cli` or `whisper-cli.exe` |
| `CELVO_WHISPER_MODEL` | Full path to the model file |
| `CELVO_LANGUAGE` | Whisper language code; defaults to `es` |

On Windows, set a variable for the current PowerShell session with `$env:CELVO_AUDIO_DIR = 'D:\Celvo Data\audio'`. Linux users can export the same variables in their shell. Celvo handles paths containing spaces.

## Audio handling and known limits

- Windows uses WASAPI loopback for the selected/default playback output, including headphones and USB/Bluetooth devices exposed by Windows. Bluetooth profiles can change sample rate or channel capabilities while in use; reconnecting or selecting a different device may be necessary.
- Linux uses `parec` with a PulseAudio monitor source and `sounddevice` for microphone capture.
- Independent input clocks are aligned from monotonic capture timestamps. The mixer converts tracks to mono 16 kHz in bounded chunks and corrects measured clock-rate mismatch across the recording. Hardware and driver timestamp quality limits alignment accuracy; real meeting-duration drift validation is still required.
- Short or silent recordings are valid WAV files when at least one source produced frames. A disconnected device, overflow, empty requested stream, or invalid WAV is reported as a failure.
- No automated test can validate a physical microphone, loopback endpoint, Bluetooth headset, or multi-hour recording. See the manual checklist for outstanding hardware checks.

## Build whisper.cpp from source

Celvo pins whisper.cpp to `v1.9.5` (commit `d1be6fde11ac6e0407606b4e42fe72d34add8037`). The Windows installer uses the official prebuilt x64 archive whose `b5454` release tag resolves to that same commit, then verifies the archive checksum. The Windows CI workflow separately builds `whisper-cli.exe` with CMake's Release configuration and packages its runtime DLLs. For a local developer build:

```powershell
git clone --depth 1 --branch v1.9.5 https://github.com/ggml-org/whisper.cpp.git
cmake -S whisper.cpp -B whisper.cpp/build -DWHISPER_BUILD_TESTS=OFF
cmake --build whisper.cpp/build --config Release --target whisper-cli --parallel
```

Linux developers can build the same pinned tag with CMake and a C++ compiler. Installers download `ggml-large-v3.bin` and verify its SHA-256 digest. This is the unquantized Large-v3 checkpoint; whisper.cpp also offers quantized variants that use less storage and memory. Large-v3 is OpenAI Whisper's largest general multilingual model in the upstream model list, but transcription quality still depends on clear audio and the configured language. [whisper.cpp model list](https://github.com/ggml-org/whisper.cpp/blob/master/models/README.md)

## Troubleshooting and uninstall

Run `celvo diagnose` first. Windows-specific fixes are documented in [the troubleshooting guide](docs/WINDOWS_TROUBLESHOOTING.md). Linux failures should include the output of `pactl list short sources` and `celvo devices` when reporting an issue.

To remove the Windows app, remove the Celvo path from your user PATH and delete `%LOCALAPPDATA%\Programs\Celvo`. Keep `%USERPROFILE%\Documents\Celvo` to retain recordings and transcripts; delete that data directory only if you intend to remove your own data. On Linux, remove `~/.local/share/celvo` and the `celvo`, `record`, and `process` launchers under `~/.local/bin`; keep `~/Documents/celvo` to retain user data.

## Project status

Linux support is retained. CI is configured for Ubuntu and Windows runners across Python 3.10–3.13. CI results and real-hardware validation are tracked separately; Windows device and long-duration checks remain pending until performed on physical hardware.

## License

MIT License. See [LICENSE](LICENSE).
