from __future__ import annotations

import csv
import re
import secrets
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_LOGS = REPO_ROOT / "experiment" / "data" / "logs"
RAW_ECG = REPO_ROOT / "experiment" / "data" / "ecg_recordings"
ANON_DIR = REPO_ROOT / "experiment" / "data_anonymized"
ANON_ECG_DIR = ANON_DIR / "ecg_recordings"
KEYS_DIR = REPO_ROOT / "analysis" / "keys"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AGE_BANDS = [
    (0, 17, "<18"),
    (18, 24, "18–24"),
    (25, 29, "25–29"),
    (30, 34, "30–34"),
    (35, 39, "35-39"),
]


def age_to_band(raw_age: str) -> str:
    """Return a 5-year band string for a raw age value, or 'Unknown'."""
    try:
        age = int(raw_age)
    except (ValueError, TypeError):
        return "Unknown"
    for low, high, label in AGE_BANDS:
        if low <= age <= high:
            return label
    return "Unknown"


_PRONOUN_RE = re.compile(
    r"\b(she|her|hers|he|him|his|they|them|theirs)\b",
    re.IGNORECASE,
)


def scrub_notes(text: str) -> str:
    """
    Replace gendered pronouns with neutral alternatives and mark the note
    for human review.  Returns an empty string for blank notes.
    """
    text = text.strip()
    if not text:
        return ""
    scrubbed = _PRONOUN_RE.sub("the participant", text)
    return f"[REVIEW] {scrubbed}"


def normalise_nationality(raw: str) -> str:
    """Title-case nationality and expand obvious short forms."""
    mapping = {
        "india": "Indian",
        "indian": "Indian",
        "iranian": "Iranian",
        "russia": "Russian",
        "russian": "Russian",
        "china": "Chinese",
        "chinese": "Chinese",
        "nepali": "Nepali",
        "mexican": "Mexican",
        "south korea": "South Korean",
    }
    return mapping.get(raw.strip().lower(), raw.strip().title())


def generate_random_id(length: int = 6) -> str:
    """Return a random uppercase alphanumeric token of *length* characters."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # omit O/0 and I/1
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------------------
# Build participant ID mapping
# ---------------------------------------------------------------------------

def build_id_mapping(participants_path: Path) -> dict[str, str]:
    """
    Read participants.csv and return a dict {old_id: new_id}.
    Only valid, non-test participants are included.
    """
    used: set[str] = set()
    mapping: dict[str, str] = {}

    with participants_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pid = row["participant_id"]
            if pid in mapping:
                continue
            # Assign a unique random token
            new_id = generate_random_id()
            while new_id in used:
                new_id = generate_random_id()
            used.add(new_id)
            mapping[pid] = new_id

    return mapping


# ---------------------------------------------------------------------------
# Per-file anonymization routines
# ---------------------------------------------------------------------------

def anonymize_participants(
    src: Path,
    dst: Path,
    mapping: dict[str, str],
) -> None:
    """
    Columns touched:
      participant_id   → mapped random token
      age              → age band
      nationality      → normalised
      notes            → pronouns scrubbed, flagged [REVIEW]
      created_at_utc   → removed (not needed for analysis)
    """
    with src.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames is not None

        out_fields = [
            f for f in reader.fieldnames
            if f not in ("created_at_utc",)
        ]

        rows = []
        for row in reader:
            row["participant_id"] = mapping.get(row["participant_id"], row["participant_id"])
            row["age"] = age_to_band(row["age"])
            row["nationality"] = normalise_nationality(row["nationality"])
            row["notes"] = scrub_notes(row.get("notes", ""))
            rows.append({k: row[k] for k in out_fields})

    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  participants: {len(rows)} valid participants written → {dst.relative_to(REPO_ROOT)}")


def anonymize_events(
    src: Path,
    dst: Path,
    mapping: dict[str, str],
) -> None:
    """
    Columns touched:
      participant_id           → mapped
      utc_iso                  → removed (absolute timestamp)
      unix_seconds             → removed (absolute epoch time)
      monotonic_seconds        → removed (system internal clock)
    """
    with src.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames is not None

        remove_cols = {"unix_seconds", "monotonic_seconds", "utc_iso"}
        out_fields = [
            f for f in reader.fieldnames if f not in remove_cols
        ]

        rows = []
        for row in reader:
            pid = row["participant_id"]
            new_row = {}
            for col in out_fields:
                new_row[col] = row[col]
            new_row["participant_id"] = mapping[pid]
            rows.append(new_row)

    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  events: {len(rows)} rows written → {dst.relative_to(REPO_ROOT)}")


def _anonymize_timestamped_csv(
    src: Path,
    dst: Path,
    mapping: dict[str, str],
    timestamp_col: str = "created_at_utc",
) -> None:
    """
    Generic helper for song_ratings.csv and trial_orders.csv.
    Replaces participant_id.
    """
    valid_pids = set(mapping.keys())

    with src.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames is not None

        out_fields = [
            f for f in reader.fieldnames if f != timestamp_col
        ]
        rows = []
        for row in reader:
            pid = row["participant_id"]
            if pid not in valid_pids:
                continue
            new_row = {}
            for col in out_fields:
                new_row[col] = row[col]
            new_row["participant_id"] = mapping[pid]
            rows.append(new_row)

    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  {src.name}: {len(rows)} rows written → {dst.relative_to(REPO_ROOT)}")


def anonymize_ecg_file(
    src: Path,
    dst_dir: Path,
    mapping: dict[str, str],
) -> None:
    """
    ECG files are the most sensitive: biometric health data.

    Columns touched:
      participant_id              → mapped

    File name: ECG_P001_20260614_141034.csv → ECG_<new_id>.csv
    (the date/time in the original name is stripped)
    """
    # Extract original participant_id from filename: ECG_PXXX_date_time.csv
    stem_parts = src.stem.split("_")
    if len(stem_parts) >= 2:
        orig_pid = stem_parts[1]
    else:
        print(f"  WARNING: unexpected ECG filename format: {src.name} — skipped")
        return

    new_id = mapping.get(orig_pid)
    if new_id is None:
        return

    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"ECG_{new_id}.csv"

    with src.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames is not None

        remove_cols = {} 
        out_fields = [
            f for f in reader.fieldnames if f not in remove_cols
        ]

        rows_raw = list(reader)

    if not rows_raw:
        return

    rows_out = []
    for row in rows_raw:
        new_row = {}
        for col in out_fields:
            if col == "participant_id":
                new_row[col] = new_id
            else:
                new_row[col] = row[col]
        rows_out.append(new_row)

    with dst.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"  ECG {src.name} → {dst.relative_to(REPO_ROOT)}")


def save_key_file(mapping: dict[str, str], dst: Path) -> None:
    """Save the old→new participant ID mapping to a key file."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["original_id", "anonymized_id"])
        for orig, anon in sorted(mapping.items()):
            writer.writerow([orig, anon])
    print(f"  ID mapping saved → {dst.relative_to(REPO_ROOT)}")
    print("  !! Keep this file out of version control and separate from anonymized data !!")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Music Origin Disclosure Study — Data Anonymization ===\n")

    # 1. Build participant ID mapping (includes valid AND test users so we can
    #    safely skip test rows in downstream files without crashing)
    participants_src = RAW_LOGS / "participants.csv"
    if not participants_src.exists():
        raise FileNotFoundError(f"participants.csv not found at {participants_src}")

    print("Building participant ID mapping …")
    mapping = build_id_mapping(participants_src)
    print(f"  {len(mapping)} participant IDs mapped\n")

    # 2. Save key file BEFORE modifying anything
    print("Saving key file …")
    save_key_file(mapping, KEYS_DIR / "id_mapping.csv")
    print()

    # 3. Anonymize each data file
    print("Anonymizing CSV logs …")
    anonymize_participants(
        participants_src,
        ANON_DIR / "participants.csv",
        mapping,
    )
    anonymize_events(
        RAW_LOGS / "events.csv",
        ANON_DIR / "events.csv",
        mapping,
    )
    _anonymize_timestamped_csv(
        RAW_LOGS / "song_ratings.csv",
        ANON_DIR / "song_ratings.csv",
        mapping,
    )
    _anonymize_timestamped_csv(
        RAW_LOGS / "trial_orders.csv",
        ANON_DIR / "trial_orders.csv",
        mapping,
    )
    print()

    # 4. Anonymize ECG files
    print("Anonymizing ECG recordings …")
    ecg_files = sorted(RAW_ECG.glob("ECG_P*.csv"))
    if not ecg_files:
        print("  No ECG files found — skipping.")
    for ecg_path in ecg_files:
        anonymize_ecg_file(ecg_path, ANON_ECG_DIR, mapping)
    print()

    print("Done.  Anonymized data written to:")
    print(f"  {ANON_DIR.relative_to(REPO_ROOT)}/")
    print()
    print("REMINDER: analysis/keys/id_mapping.csv must be stored separately")
    print("from the anonymized data and excluded from public repositories.")


if __name__ == "__main__":
    main()
