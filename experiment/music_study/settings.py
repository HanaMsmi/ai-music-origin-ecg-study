from pathlib import Path


EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
STIMULI_DIR = EXPERIMENT_DIR / "stimuli"
EXPERIMENT_STIMULI_DIR = STIMULI_DIR / "experiment"
PRACTICE_STIMULI_DIR = STIMULI_DIR / "practice"
LOG_DIR = EXPERIMENT_DIR / "data" / "logs"

BACKGROUND_COLOR = "#cfcfcf"
TEXT_COLOR = "black"
ACCENT_COLOR = "#2c5282"
GUIDE_PANEL_COLOR = "#e8e8e8"

REST_SECONDS = 30

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aiff", ".aif", ".flac", ".ogg"}

ORIGIN_AI = "AI-generated"
ORIGIN_HUMAN = "Human composed"

PARTICIPANT_FIELDS = [
    "participant_name",
    "nationality",
    "age",
    "music_training_years",
    "music_listening_frequency",
    "music_knowledge",
    "ai_familiarity",
    "knowingly_heard_ai_music",
    "used_music_generation_tool",
    "attitude_ai_music",
    "ai_creativity",
    "created_at_utc",
]

TRIAL_ORDER_FIELDS = [
    "participant_name",
    "created_at_utc",
    "trial_index",
    "song_file",
    "song_title",
    "true_origin",
    "shown_origin",
    "mislabeled",
    "duration_seconds",
]

EVENT_FIELDS = [
    "utc_iso",
    "unix_seconds",
    "monotonic_seconds",
    "participant_name",
    "phase",
    "trial_index",
    "event",
    "song_file",
    "true_origin",
    "shown_origin",
    "mislabeled",
    "details",
]

RATING_FIELDS = [
    "participant_name",
    "created_at_utc",
    "trial_index",
    "song_file",
    "song_title",
    "true_origin",
    "shown_origin",
    "mislabeled",
    "enjoy_before_origin",
    "enjoy_after_origin",
    "musical_quality",
    "surprised_by_origin",
    "origin_changed_experience",
]

LIKERT_7 = [
    "Not at all",
    "Very little",
    "Slightly",
    "Moderately",
    "Quite a lot",
    "Very much",
    "Extremely",
]

LISTENING_FREQUENCY = [
    "Rarely",
    "A few times per month",
    "A few times per week",
    "Daily",
    "Many times per day",
]

YES_NO_UNSURE = ["Yes", "No", "Not sure"]
YES_NO = ["Yes", "No"]
