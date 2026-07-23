from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write


SAMPLE_RATE = 48000
CHANNELS = 1


def record_microphone(output: Path, stop_event):
    frames = []

    def callback(indata, frames_count, time, status):
        frames.append(indata.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=np.int16,
        callback=callback,
    ):
        while not stop_event.is_set():
            stop_event.wait(0.1)

    audio = np.concatenate(frames)

    write(
        output,
        SAMPLE_RATE,
        audio,
    )
