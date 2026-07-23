from datetime import datetime

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

from .config import AUDIO_DIR, ensure_directories


SAMPLE_RATE = 44100
CHANNELS = 1


def record_audio(duration):
    ensure_directories()

    filename = datetime.now().strftime("recording_%Y%m%d_%H%M%S.wav")
    output = AUDIO_DIR / filename

    print("Recording...")

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

    print(f"Saved: {output}")

    return output
