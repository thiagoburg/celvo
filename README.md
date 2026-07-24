# Celvo

![Celvo Demo](docs/images/demo.png)

Private, offline audio recording and transcription tool for Linux.

Built on `whisper.cpp` for high-quality local transcription.

Celvo records audio locally and generates accurate transcriptions completely offline.

Your recordings never leave your machine.

---

# Installation

## Quick install

Copy and paste this into your terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/thiagoburg/celvo/main/install.sh | bash
```

The installer automatically:

✓ Detects your Linux distribution  
✓ Installs required dependencies  
✓ Creates the Python environment  
✓ Builds whisper.cpp  
✓ Downloads the Whisper model  
✓ Creates the Celvo commands  

After installation:

```bash
record
```

Record your audio, then:

```bash
process
```

Generate your transcription.

---

# Tested systems

## Fedora Linux

Tested on:

- Fedora Linux
- Python 3.14
- whisper.cpp
- Whisper Large-v3 quantized model

Installation validated successfully.

![Fedora Installation](docs/images/fedora.png)


## Ubuntu Linux

Testing in progress.

Installation validation coming soon.

![Ubuntu Installation](docs/images/ubuntu.png)

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

Celvo is designed for transcription quality, privacy and reliability.

It does not summarize, rewrite, or interpret conversations.

---

# Privacy

Everything runs locally.

Your audio is:

- recorded locally
- processed locally
- transcribed locally

Nothing is uploaded to external servers.

No internet connection is required after installation.

Internet is only required during the first installation to download dependencies and the transcription model.

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

Upcoming improvements:

- More robust installer
- Better error messages
- Automatic tests
- Improved documentation
- Additional Linux validation
- Stable release

---

# Project status

Current version: **v1.1.2**

The installation process has been validated on Fedora Linux.

Ubuntu and additional Linux distributions are currently being tested.

---

# License

MIT License
