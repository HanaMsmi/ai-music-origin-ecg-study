import random
import re
import subprocess
from hashlib import sha256
from pathlib import Path

from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.wave import WAVE

from music_study.settings import (
    AUDIO_EXTENSIONS,
    EXPERIMENT_STIMULI_DIR,
    ORIGIN_AI,
    ORIGIN_HUMAN,
    PRACTICE_STIMULI_DIR,
)
from music_study.time_utils import utc_now
from music_study.trial import Trial


_MUTAGEN_CLASS = {
    ".mp3": MP3,
    ".wav": WAVE,
    ".flac": FLAC,
    ".m4a": MP4,
    ".aac": MP4,
    ".mp4": MP4,
}


def audio_duration(path: Path) -> float:
    cls = _MUTAGEN_CLASS.get(path.suffix.lower())
    if cls is None:
        raise ValueError(f"Unsupported audio format: {path.suffix} ({path})")
    try:
        return float(cls(path).info.length)
    except Exception as e:
        raise ValueError(f"Could not determine duration for {path}: {e}") from None


def audio_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS)


def make_trials(participant_name: str) -> list[Trial]:
    """Build the trial list from AI-generated songs only.

    Half of the songs receive a truthful AI label; the other half are mislabeled
    as human composed. All audio is AI-generated.
    """
    song_paths = audio_files(EXPERIMENT_STIMULI_DIR)
    seed = int(sha256(f"{participant_name}-{utc_now()}".encode("utf-8")).hexdigest(), 16)
    rng = random.Random(seed)

    rng.shuffle(song_paths)
    mislabeled_count = len(song_paths) // 2
    mislabeled_paths = set(rng.sample(song_paths, k=mislabeled_count)) if song_paths else set()

    trials: list[Trial] = []
    for path in song_paths:
        mislabeled = path in mislabeled_paths
        shown_origin = ORIGIN_HUMAN if mislabeled else ORIGIN_AI
        duration = audio_duration(path)
        trials.append(Trial(path, ORIGIN_AI, shown_origin, mislabeled, duration))

    return trials


def make_practice_trial() -> Trial | None:
    practice_files = audio_files(PRACTICE_STIMULI_DIR)
    if not practice_files:
        raise ValueError("No practice audio files found")

    path = practice_files[0]
    duration = audio_duration(path)
    return Trial(path, ORIGIN_AI, ORIGIN_HUMAN, True, duration)
