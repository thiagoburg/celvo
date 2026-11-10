from __future__ import annotations

import importlib
from pathlib import Path

from celvo.core.audio.base import AudioDevice
from celvo.main import main


def test_environment_paths_are_honored(monkeypatch, tmp_path):
    monkeypatch.setenv("CELVO_DATA_DIR", str(tmp_path / "data with spaces"))
    import celvo.core.config as config

    importlib.reload(config)
    assert config.AUDIO_DIR == tmp_path / "data with spaces" / "audio"
    assert config.OUTPUT_DIR == tmp_path / "data with spaces" / "transcription"
    monkeypatch.delenv("CELVO_DATA_DIR")
    importlib.reload(config)


def test_relative_overrides_are_independent_of_working_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("CELVO_AUDIO_DIR", "recordings with spaces")
    import celvo.core.config as config
    importlib.reload(config)
    assert config.AUDIO_DIR == Path.home() / "recordings with spaces"
    monkeypatch.delenv("CELVO_AUDIO_DIR")
    importlib.reload(config)


def test_windows_default_uses_documents_celvo(monkeypatch):
    monkeypatch.delenv("CELVO_DATA_DIR", raising=False)
    import celvo.core.config as config

    original_platform = config.sys.platform
    try:
        config.sys.platform = "win32"
        importlib.reload(config)
        assert config.DATA_DIR == Path.home() / "Documents" / "Celvo"
        assert config.AUDIO_DIR == Path.home() / "Documents" / "Celvo" / "audio"
        assert config.OUTPUT_DIR == Path.home() / "Documents" / "Celvo" / "transcription"
    finally:
        config.sys.platform = original_platform
        importlib.reload(config)


def test_executable_and_model_path_overrides_support_spaces(monkeypatch, tmp_path):
    import celvo.core.config as config
    executable = tmp_path / "program files" / "whisper-cli.exe"
    model = tmp_path / "large model" / "model.bin"
    monkeypatch.setenv("CELVO_WHISPER_CLI", str(executable))
    monkeypatch.setenv("CELVO_WHISPER_MODEL", str(model))
    importlib.reload(config)
    assert config.WHISPER_CLI == executable
    assert config.WHISPER_MODEL == model
    monkeypatch.delenv("CELVO_WHISPER_CLI")
    monkeypatch.delenv("CELVO_WHISPER_MODEL")
    importlib.reload(config)


def test_model_discovery_prefers_full_precision_then_uses_existing_q5(monkeypatch, tmp_path):
    import celvo.core.config as config

    model_dir = tmp_path / "models"
    model_dir.mkdir()
    monkeypatch.setattr(config, "MODEL_DIR", model_dir)
    full = model_dir / "ggml-large-v3.bin"
    quantized = model_dir / "ggml-large-v3-q5_0.bin"
    quantized.touch()
    assert config.discover_model() == quantized
    full.touch()
    assert config.discover_model() == full


def test_help_version_and_invalid_command(capsys):
    assert main(["--help"]) == 0
    assert "devices" in capsys.readouterr().out
    assert main(["--version"]) == 0
    assert "Celvo" in capsys.readouterr().out


def test_devices_command_reports_backend(monkeypatch, capsys):
    import celvo.main as cli

    class FakeBackend:
        def list_devices(self):
            return [AudioDevice(2, "Built in microphone", "microphone", True)]

    monkeypatch.setattr(cli, "get_audio_backend", lambda: FakeBackend())
    assert cli.main(["devices"]) == 0
    assert "Built in microphone" in capsys.readouterr().out


def test_process_failure_has_nonzero_exit_code(monkeypatch, capsys):
    import celvo.main as cli

    monkeypatch.setattr(cli, "process_latest", lambda: (_ for _ in ()).throw(RuntimeError("missing model")))
    assert cli.main(["process"]) == 1
    assert "missing model" in capsys.readouterr().err
