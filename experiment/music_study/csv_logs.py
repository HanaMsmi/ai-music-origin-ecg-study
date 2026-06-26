import csv
from pathlib import Path

from music_study.settings import (
    EVENT_FIELDS,
    EXPERIMENT_STIMULI_DIR,
    LOG_DIR,
    PARTICIPANT_FIELDS,
    PRACTICE_STIMULI_DIR,
    RATING_FIELDS,
    TRIAL_ORDER_FIELDS,
)
from music_study.time_utils import monotonic_seconds, unix_seconds, utc_now
from music_study.trial import Trial


def ensure_directories() -> None:
    for directory in (EXPERIMENT_STIMULI_DIR, PRACTICE_STIMULI_DIR, LOG_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def ensure_csv(path: Path, fieldnames: list[str]) -> None:
    if path.exists() and path.stat().st_size > 0:
        with path.open("r", newline="", encoding="utf-8") as csv_file:
            current_header = next(csv.reader(csv_file), [])
        if current_header == fieldnames:
            return
        backup_path = path.with_suffix(path.suffix + f".backup-{utc_now().replace(':', '-')}")
        path.rename(backup_path)

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        csv.DictWriter(csv_file, fieldnames=fieldnames).writeheader()


def ensure_logs() -> None:
    ensure_csv(LOG_DIR / "participants.csv", PARTICIPANT_FIELDS)
    ensure_csv(LOG_DIR / "trial_orders.csv", TRIAL_ORDER_FIELDS)
    ensure_csv(LOG_DIR / "events.csv", EVENT_FIELDS)
    ensure_csv(LOG_DIR / "song_ratings.csv", RATING_FIELDS)


def append_csv(path: Path, fieldnames: list[str], row: dict[str, object]) -> None:
    with path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writerow({field: row.get(field, "") for field in fieldnames})


def log_event(
    participant_name: str,
    phase: str,
    event_name: str,
    trial_index: int | None = None,
    trial: Trial | None = None,
    details: str = "",
) -> None:
    append_csv(
        LOG_DIR / "events.csv",
        EVENT_FIELDS,
        {
            "utc_iso": utc_now(),
            "unix_seconds": unix_seconds(),
            "monotonic_seconds": monotonic_seconds(),
            "participant_name": participant_name,
            "phase": phase,
            "trial_index": trial_index if trial_index is not None else "",
            "event": event_name,
            "song_file": trial.relative_path if trial else "",
            "true_origin": trial.true_origin if trial else "",
            "shown_origin": trial.shown_origin if trial else "",
            "mislabeled": trial.mislabeled if trial else "",
            "details": details,
        },
    )


def save_participant(responses: dict[str, str], created_at_utc: str) -> None:
    row = dict(responses)
    row["created_at_utc"] = created_at_utc
    append_csv(LOG_DIR / "participants.csv", PARTICIPANT_FIELDS, row)


def save_trial_order(participant_name: str, trials: list[Trial], created_at_utc: str) -> None:
    for index, trial in enumerate(trials, start=1):
        append_csv(
            LOG_DIR / "trial_orders.csv",
            TRIAL_ORDER_FIELDS,
            {
                "participant_name": participant_name,
                "created_at_utc": created_at_utc,
                "trial_index": index,
                "song_file": trial.relative_path,
                "song_title": trial.song_title,
                "true_origin": trial.true_origin,
                "shown_origin": trial.shown_origin,
                "mislabeled": trial.mislabeled,
                "duration_seconds": trial.duration_seconds,
            },
        )


def save_ratings(participant_name: str, trial_index: int, trial: Trial, ratings: dict[str, str]) -> None:
    row = {
        "participant_name": participant_name,
        "created_at_utc": utc_now(),
        "trial_index": trial_index,
        "song_file": trial.relative_path,
        "song_title": trial.song_title,
        "true_origin": trial.true_origin,
        "shown_origin": trial.shown_origin,
        "mislabeled": trial.mislabeled,
    }
    row.update(ratings)
    append_csv(LOG_DIR / "song_ratings.csv", RATING_FIELDS, row)
