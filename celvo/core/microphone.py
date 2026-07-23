from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write


SAMPLE_RATE = 48000
CHANNELS = 1


def record_microphone(output: Path, duration: int):
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=np.int16,
    )

    sd.wait()

    write(
        output,
        SAMPLE_RATE,
        audio,
    )
