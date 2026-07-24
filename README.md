# Celvo

Private, offline audio recording and transcription for Linux.

Built on `whisper.cpp` for high-quality local transcription.

**Celvo** is a local audio recording and transcription tool focused on **privacy, simplicity, and transcription quality**.

It records audio on your computer and transcribes it entirely offline using **whisper.cpp** and OpenAI's Whisper models. Your recordings never leave your machine.

---

# Features

- Local audio recording
- Offline AI transcription
- Powered by `whisper.cpp`
- Whisper Large-v3 quantized model
- No cloud services
- No API keys
- No subscriptions
- Simple command-line interface
- High-quality transcription

Celvo is designed to transcribe audio as accurately as possible.

It does **not** summarize, rewrite, or interpret conversations.

---

# Privacy

Everything runs locally.

Your audio is:

- recorded locally
- processed locally
- transcribed locally

Nothing is uploaded to external servers.

No internet connection is required after installation.

An internet connection is only required during the initial installation to download dependencies and the transcription model.

---

# How it works

Celvo follows a simple workflow:

1. Record audio.
2. Save the recording locally.
3. Run Whisper locally using `whisper.cpp`.
4. Generate a text transcription.

The transcription is produced entirely on your own computer.

---

# Requirements

Celvo requires:

- Python 3
- Git
- CMake
- A C++ compiler
- Standard Linux development tools

The installer automatically installs the required dependencies whenever possible.

---

# Supported systems

**Tested on Fedora Linux.**

It should work on other major Linux distributions, but they have not yet been fully validated.

Planned testing includes:

- Ubuntu
- Debian
- Arch Linux

---

# Installation

## Copy and paste this into your terminal

```bash
curl -fsSL https://raw.githubusercontent.com/thiagoburg/celvo/main/install.sh | bash
```

## What the installer does

The installer automatically:

- Detects your Linux distribution.
- Installs required system packages.
- Creates a Python virtual environment.
- Installs Python dependencies.
- Installs the Celvo Python package.
- Downloads and builds `whisper.cpp`.
- Downloads the Whisper Large-v3 quantized model.
- Creates the Celvo commands.

The first installation takes several minutes because it compiles `whisper.cpp` and downloads approximately **1 GB** of model files.

---

# Available commands

After installation, these commands are available:

```bash
record
```

Starts a new audio recording.

```bash
process
```

Processes the recorded audio and generates the transcription.

---

# Project goals

Celvo aims to provide a professional local transcription workflow that is:

- Private
- Offline
- Reliable
- Easy to install
- Easy to use

The primary goal is **transcription quality**, not AI-assisted content generation.

---

# Technology

Celvo is built with:

- Python
- whisper.cpp
- Whisper Large-v3
- sounddevice
- numpy
- scipy
- requests

---

# Roadmap

Upcoming improvements include:

- More robust installer
- Better error messages
- Automatic tests
- Improved documentation
- Additional Linux validation
- Stable release

---

# Project status

Current version: **v1.1.0**

The installation process has been validated on Fedora Linux.

Support for additional Linux distributions is currently being tested.

---

# License

MIT License

