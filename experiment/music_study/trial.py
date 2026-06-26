from dataclasses import dataclass
from pathlib import Path

from music_study.settings import EXPERIMENT_DIR


@dataclass
class Trial:
    path: Path
    true_origin: str
    shown_origin: str
    mislabeled: bool
    duration_seconds: float

    @property
    def song_title(self) -> str:
        return self.path.stem

    @property
    def relative_path(self) -> str:
        return str(self.path.relative_to(EXPERIMENT_DIR))
