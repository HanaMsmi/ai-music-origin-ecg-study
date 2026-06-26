import ctypes
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from typing import Any

from music_study.csv_logs import log_event, save_ratings
from music_study.settings import (
    ACCENT_COLOR,
    BACKGROUND_COLOR,
    GUIDE_PANEL_COLOR,
    LIKERT_7,
    LISTENING_FREQUENCY,
    REST_SECONDS,
    TEXT_COLOR,
    YES_NO,
    YES_NO_UNSURE,
)
from music_study.stimuli import make_practice_trial
from music_study.trial import Trial

BACK = object()

_MCI_ALIAS = "music_study_song"


class _AudioPlayer:
    """Cross-platform audio player.

    Call preload() as early as possible (e.g. during the fixation rest screen)
    so the file is buffered before start() is invoked.
    poll() mirrors subprocess.Popen.poll(): None = still playing, 0 = done.
    """

    def preload(self) -> None:
        """Open/buffer the file without starting playback yet."""

    def start(self) -> None:
        """Begin playback. Call after preload()."""
        raise NotImplementedError

    def poll(self) -> int | None:
        raise NotImplementedError


class _MacAudioPlayer(_AudioPlayer):
    def __init__(self, path: Path) -> None:
        self._path = path
        self._proc: subprocess.Popen | None = None

    # afplay starts instantly on macOS; no preloading needed.
    def start(self) -> None:
        self._proc = subprocess.Popen(["afplay", str(self._path)])

    def poll(self) -> int | None:
        return self._proc.poll() if self._proc else 0


class _WinAudioPlayer(_AudioPlayer):
    """Uses the Windows MCI API (winmm.dll) — no subprocess, no startup delay."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._done = False
        self._winmm = ctypes.WinDLL("winmm")

    def preload(self) -> None:
        """Open the file in MCI so it is buffered before playback starts."""
        self._winmm.mciSendStringW(f"close {_MCI_ALIAS}", None, 0, None)
        self._winmm.mciSendStringW(
            f'open "{self._path}" alias {_MCI_ALIAS}', None, 0, None
        )

    def start(self) -> None:
        """Start playback — near-instant because preload() already opened the file."""
        self._winmm.mciSendStringW(f"play {_MCI_ALIAS}", None, 0, None)

    def poll(self) -> int | None:
        if self._done:
            return 0
        buf = ctypes.create_unicode_buffer(32)
        self._winmm.mciSendStringW(
            f"status {_MCI_ALIAS} mode", buf, len(buf), None
        )
        if buf.value == "playing":
            return None
        self._winmm.mciSendStringW(f"close {_MCI_ALIAS}", None, 0, None)
        self._done = True
        return 0


def _prepare_audio(path: Path) -> _AudioPlayer:
    """Create and preload a player for the given file. Call start() when ready to play."""
    player: _AudioPlayer = _MacAudioPlayer(path) if sys.platform == "darwin" else _WinAudioPlayer(path)
    player.preload()
    return player


PRACTICE_STEPS = [
    ("Rest", "A fixation cross (+) appears while you take a short break between songs."),
    (
        "Listen",
        "The song plays. Halfway through, you will see the origin (AI-generated or human composed) of the song.",
    ),
    ("Questions", "After the song ends, you answer a short questionnaire about what you heard."),
]


class ExperimentApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Music Origin Study")
        self.root.configure(bg=BACKGROUND_COLOR)
        self.root.attributes("-fullscreen", True)
        self.participant_name = ""

    def clear(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()

    def centered_content(self) -> tk.Frame:
        outer = tk.Frame(self.root, bg=BACKGROUND_COLOR)
        outer.pack(expand=True, fill="both")
        content = tk.Frame(outer, bg=BACKGROUND_COLOR)
        content.place(relx=0.5, rely=0.5, anchor="center")
        return content

    def make_label(
        self,
        parent: tk.Misc,
        text: str,
        font_size: int = 28,
        color: str = TEXT_COLOR,
        wrap: int = 900,
    ) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=BACKGROUND_COLOR,
            fg=color,
            font=("Helvetica", font_size),
            wraplength=wrap,
            justify="center",
        )

    def wait_screen(
        self,
        text: str,
        seconds: float | None = None,
        button_text: str | None = "Continue",
        subtitle: str = "",
    ) -> None:
        self.clear()
        content = self.centered_content()

        if subtitle:
            self.make_label(content, subtitle, font_size=20, color=ACCENT_COLOR).pack(pady=(0, 10))

        self.make_label(content, text).pack(pady=20)

        done = tk.BooleanVar(value=False)
        if button_text is not None:
            tk.Button(content, text=button_text, font=("Helvetica", 20), command=lambda: done.set(True)).pack(pady=20)
            self.root.bind("<space>", lambda _event: done.set(True))

        if seconds is not None:
            self.root.after(int(seconds * 1000), lambda: done.set(True))

        self.root.wait_variable(done)
        self.root.unbind("<space>")

    def show_practice_guide(self, step_index: int) -> None:
        title, description = PRACTICE_STEPS[step_index]
        self.wait_screen(
            f"Practice — Step {step_index + 1} of {len(PRACTICE_STEPS)}\n\n{title}\n\n{description}",
            button_text="Next",
        )

    def show_flow_overview(self) -> None:
        self.clear()
        outer = tk.Frame(self.root, bg=BACKGROUND_COLOR)
        outer.pack(expand=True, fill="both")

        canvas_frame = tk.Frame(outer, bg=BACKGROUND_COLOR)
        canvas_frame.pack(expand=True, fill="both", padx=40, pady=(30, 10))

        self.make_label(canvas_frame, "What happens in each trial?", font_size=32).pack(pady=(0, 24))

        for index, (title, description) in enumerate(PRACTICE_STEPS):
            step_frame = tk.Frame(canvas_frame, bg=GUIDE_PANEL_COLOR, padx=20, pady=14)
            step_frame.pack(fill="x", pady=6)

            tk.Label(
                step_frame,
                text=f"{index + 1}. {title}",
                bg=GUIDE_PANEL_COLOR,
                fg=ACCENT_COLOR,
                font=("Helvetica", 20, "bold"),
                anchor="center",
                justify="center",
            ).pack(fill="x")
            tk.Label(
                step_frame,
                text=description,
                bg=GUIDE_PANEL_COLOR,
                fg=TEXT_COLOR,
                font=("Helvetica", 16),
                wraplength=860,
                justify="center",
                anchor="center",
            ).pack(fill="x", pady=(4, 0))

        button_frame = tk.Frame(outer, bg=BACKGROUND_COLOR)
        button_frame.pack(pady=(10, 30))

        done = tk.BooleanVar(value=False)
        tk.Button(button_frame, text="Start practice", font=("Helvetica", 20), command=lambda: done.set(True)).pack()
        self.root.bind("<space>", lambda _event: done.set(True))
        self.root.wait_variable(done)
        self.root.unbind("<space>")

    def fixation(self, seconds: float) -> None:
        self.clear()
        content = self.centered_content()
        self.make_label(content, "+", font_size=64).pack()

        done = tk.BooleanVar(value=False)
        self.root.after(int(seconds * 1000), lambda: done.set(True))
        self.root.wait_variable(done)

    def ask_text(self, prompt: str, optional: bool = False, allow_back: bool = False) -> str | object:
        self.clear()
        content = self.centered_content()
        self.make_label(content, prompt, font_size=24).pack(pady=20)

        entry = tk.Entry(content, font=("Helvetica", 22), width=42, justify="center")
        entry.pack(pady=20)
        entry.focus_set()

        done = tk.BooleanVar(value=False)
        went_back = {"value": False}
        result = {"value": ""}

        def submit() -> None:
            value = entry.get().strip()
            if value or optional:
                result["value"] = value
                done.set(True)

        def go_back() -> None:
            went_back["value"] = True
            done.set(True)

        buttons = tk.Frame(content, bg=BACKGROUND_COLOR)
        buttons.pack(pady=10)

        if allow_back:
            tk.Button(buttons, text="Back", font=("Helvetica", 18), width=10, command=go_back).pack(side="left", padx=8)
        tk.Button(buttons, text="Continue", font=("Helvetica", 18), width=10, command=submit).pack(side="left", padx=8)

        self.root.bind("<Return>", lambda _event: submit())
        self.root.wait_variable(done)
        self.root.unbind("<Return>")

        if went_back["value"]:
            return BACK
        return result["value"]

    def ask_choice(
        self,
        prompt: str,
        options: list[str],
        allow_back: bool = False,
    ) -> str | object:
        self.clear()
        content = self.centered_content()
        self.make_label(content, prompt, font_size=23).pack(pady=20)

        done = tk.BooleanVar(value=False)
        went_back = {"value": False}
        result = {"value": ""}

        options_frame = tk.Frame(content, bg=BACKGROUND_COLOR)
        options_frame.pack(pady=10)

        for option in options:
            tk.Button(
                options_frame,
                text=option,
                font=("Helvetica", 17),
                width=36,
                command=lambda value=option: (result.update(value=value), done.set(True)),
            ).pack(pady=5)

        if allow_back:
            tk.Button(
                content,
                text="Back",
                font=("Helvetica", 18),
                width=10,
                command=lambda: (went_back.update(value=True), done.set(True)),
            ).pack(pady=(16, 0))

        self.root.wait_variable(done)
        if went_back["value"]:
            return BACK
        return result["value"]

    def run_questionnaire(self, questions: list[dict[str, Any]], intro: str | None = None) -> dict[str, str]:
        if intro:
            self.wait_screen(intro)

        answers: dict[str, str] = {}
        index = 0

        while index < len(questions):
            question = questions[index]
            allow_back = index > 0

            if question["type"] == "text":
                result = self.ask_text(question["prompt"], question.get("optional", False), allow_back=allow_back)
            else:
                result = self.ask_choice(question["prompt"], question["options"], allow_back=allow_back)

            if result is BACK:
                index -= 1
                continue

            answers[question["key"]] = str(result)
            index += 1

        return answers

    def initial_questionnaire(self) -> dict[str, str]:
        return self.run_questionnaire(
            [
                {"type": "text", "key": "participant_name", "prompt": "What is your name?"},
                {"type": "text", "key": "nationality", "prompt": "What is your nationality?"},
                {"type": "text", "key": "age", "prompt": "Age"},
                {"type": "text", "key": "music_training_years", "prompt": "How many years of formal music training do you have?"},
                {
                    "type": "choice",
                    "key": "music_listening_frequency",
                    "prompt": "How often do you intentionally listen to music?",
                    "options": LISTENING_FREQUENCY,
                },
                {
                    "type": "choice",
                    "key": "music_knowledge",
                    "prompt": "How would you rate your knowledge about music and songs?",
                    "options": LIKERT_7,
                },
                {
                    "type": "choice",
                    "key": "ai_familiarity",
                    "prompt": "How familiar are you with artificial intelligence tools?",
                    "options": LIKERT_7,
                },
                {
                    "type": "choice",
                    "key": "knowingly_heard_ai_music",
                    "prompt": "Have you knowingly listened to AI-generated music before?",
                    "options": YES_NO_UNSURE,
                },
                {
                    "type": "choice",
                    "key": "used_music_generation_tool",
                    "prompt": "Have you ever used a tool to generate music?",
                    "options": YES_NO,
                },
                {
                    "type": "choice",
                    "key": "attitude_ai_music",
                    "prompt": "Before this study, how positive was your attitude toward AI-generated music?",
                    "options": LIKERT_7,
                },
                {
                    "type": "choice",
                    "key": "ai_creativity",
                    "prompt": "To what extent do you think AI can be musically creative?",
                    "options": LIKERT_7,
                },
            ],
            intro="Initial questionnaire\n\nPlease answer the following background questions.",
        )

    def song_questionnaire(self, practice: bool = False) -> dict[str, str]:
        intro = None if practice else "Song questionnaire\n\nPlease answer the following questions about the song you just heard."
        return self.run_questionnaire(
            [
                {
                    "type": "choice",
                    "key": "enjoy_before_origin",
                    "prompt": "Before the origin was shown, how much did you enjoy the music?",
                    "options": LIKERT_7,
                },
                {
                    "type": "choice",
                    "key": "enjoy_after_origin",
                    "prompt": "After the origin was shown, how much did you enjoy the music?",
                    "options": LIKERT_7,
                },
                {
                    "type": "choice",
                    "key": "musical_quality",
                    "prompt": "How would you rate the musical quality of this song?",
                    "options": LIKERT_7,
                },
                {
                    "type": "choice",
                    "key": "surprised_by_origin",
                    "prompt": "How surprised were you by the shown origin?",
                    "options": LIKERT_7,
                },
                {
                    "type": "choice",
                    "key": "origin_changed_experience",
                    "prompt": "How much did seeing the origin change your experience of the song?",
                    "options": LIKERT_7,
                },
            ],
            intro=intro,
        )

    def play_trial(
        self,
        trial: Trial,
        trial_index: int,
        phase: str = "main",
        player: _AudioPlayer | None = None,
    ) -> None:
        midpoint_seconds = trial.duration_seconds / 2.0

        if player is None:
            player = _prepare_audio(trial.path)

        self.clear()
        content = self.centered_content()
        display = self.make_label(content, "+", font_size=64)
        display.pack()
        self.root.update_idletasks()

        log_event(self.participant_name, phase, "song_listen_started", trial_index, trial)
        started = time.monotonic()
        player.start()
        process = player
        done = tk.BooleanVar(value=False)
        midpoint_shown = False

        def update() -> None:
            nonlocal midpoint_shown
            elapsed = time.monotonic() - started

            if not midpoint_shown and elapsed >= midpoint_seconds:
                midpoint_shown = True
                log_event(
                    self.participant_name,
                    phase,
                    "origin_shown",
                    trial_index,
                    trial,
                    details=f"midpoint_seconds={midpoint_seconds:.3f}",
                )
                display.config(
                    text=f"Origin: {trial.shown_origin}",
                    font=("Helvetica", 36),
                    fg=TEXT_COLOR,
                )

            if process.poll() is None:
                self.root.after(20, update)
                return

            log_event(
                self.participant_name,
                phase,
                "song_listen_finished",
                trial_index,
                trial,
                details=f"elapsed={elapsed:.3f}",
            )
            done.set(True)

        update()
        self.root.wait_variable(done)

    def run_practice_phase(self) -> None:
        log_event(self.participant_name, "practice", "practice_started")
        self.wait_screen(
            "Practice phase\n\n"
            "Please stay quiet during rest and while music is playing.\n"
            "You may speak only when answering the questionnaire.\n\n"
            "You will walk through one example trial step by step.\n"
            "Your practice answers are not saved.",
        )
        self.show_flow_overview()

        practice_trial = make_practice_trial()
        if not practice_trial:
            self.wait_screen(
                "No practice audio found.\n\nAdd a file to experiment/stimuli/practice/, then restart.",
            )
            log_event(self.participant_name, "practice", "practice_finished", details="No practice audio.")
            return

        self.show_practice_guide(0)
        practice_player = _prepare_audio(practice_trial.path)
        self.fixation(3)
        log_event(self.participant_name, "practice", "practice_fixation_completed")

        self.show_practice_guide(1)
        self.play_trial(practice_trial, 0, "practice", player=practice_player)

        self.show_practice_guide(2)
        self.song_questionnaire(practice=True)
        log_event(self.participant_name, "practice", "practice_questionnaire_completed", details="Practice answers were not saved.")

        self.wait_screen(
            "Practice complete\n\nYou are ready for the main experiment."
        )
        log_event(self.participant_name, "practice", "practice_finished")

    def run_main_experiment(self, trials: list[Trial]) -> None:
        self.wait_screen(
            "Main experiment\n\n"
            f"You will hear {len(trials)} songs.\n"
            "For each song, you go through the same steps as in the practice phase."
        )
        log_event(self.participant_name, "main", "main_experiment_started")

        for index, trial in enumerate(trials, start=1):
            log_event(self.participant_name, "main", "fixation_started", index, trial)
            player = _prepare_audio(trial.path)  # preload during rest so start() is instant
            self.fixation(REST_SECONDS)
            log_event(self.participant_name, "main", "fixation_finished", index, trial)

            self.play_trial(trial, index, player=player)

            ratings = self.song_questionnaire()
            save_ratings(self.participant_name, index, trial, ratings)
            log_event(self.participant_name, "main", "song_questionnaire_submitted", index, trial)

        log_event(self.participant_name, "main", "main_experiment_finished")
        self.wait_screen("The experiment is complete.\n\nThank you.", seconds=4, button_text=None)
