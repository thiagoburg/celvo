from pathlib import Path

import numpy as np
from scipy.io.wavfile import read, write


SYSTEM_RATE = 48000


def mix_audio(microphone_file: Path, system_file: Path, output: Path):
    mic_rate, mic = read(microphone_file)

    system = np.fromfile(
        system_file,
        dtype=np.int16,
    )

    system = system.reshape(-1, 2)
    system = system.mean(axis=1).astype(np.int16)

    length = min(len(mic), len(system))

    mixed = (
        mic[:length].astype(np.int32)
        + system[:length].astype(np.int32)
    )

    mixed = np.clip(
        mixed,
        -32768,
        32767,
    ).astype(np.int16)

    write(
        output,
        mic_rate,
        mixed,
    )
