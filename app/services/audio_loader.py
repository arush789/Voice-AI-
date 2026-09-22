import logging
import subprocess
from pathlib import Path
import librosa
import numpy as np
import soundfile as sf

logger = logging.getLogger("rakhsha.audio_loader")

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception as e:
    logger.warning(f"imageio_ffmpeg not found: {e}. Falling back to system 'ffmpeg'.")
    FFMPEG_EXE = "ffmpeg"


def load_audio_16k(audio_path: str) -> np.ndarray:
    """
    Loads any audio format (.wav, .m4a, .mp3, .webm, .ogg, etc.),
    converts stereo to mono, resamples to exactly 16 kHz,
    and returns a 1D float32 numpy array.
    """
    file_path = str(audio_path)

    # 1. Try soundfile first (fastest for WAV, FLAC, OGG)
    try:
        audio, sample_rate = sf.read(file_path, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sample_rate != 16000:
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
        return audio.astype(np.float32)
    except Exception:
        # soundfile does not support m4a/aac/webm out of the box on Windows
        pass

    # 2. Universal fallback via FFmpeg pipe (handles m4a, webm, aac, mp3, amr, etc.)
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-i", file_path,
        "-f", "f32le",
        "-acodec", "pcm_f32le",
        "-ac", "1",
        "-ar", "16000",
        "-"
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, check=True)
        audio = np.frombuffer(proc.stdout, dtype=np.float32).copy()
        if len(audio) == 0:
            raise ValueError(f"Decoded audio stream is empty for file: {file_path}")
        return audio
    except subprocess.CalledProcessError as e:
        stderr_msg = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        logger.error(f"FFmpeg failed to decode {file_path}: {stderr_msg}")
        raise RuntimeError(f"Failed to decode audio file {file_path}: {stderr_msg}")
