import sys
from tkinter import messagebox

from music_study.csv_logs import ensure_directories, ensure_logs, log_event, save_participant, save_trial_order
from music_study.screens import ExperimentApp
from music_study.stimuli import make_trials
from music_study.time_utils import utc_now


def main() -> int:
    ensure_directories()
    ensure_logs()

    app = ExperimentApp()

    created_at_utc = utc_now()
    responses = app.initial_questionnaire()
    app.participant_name = responses["participant_name"]

    save_participant(responses, created_at_utc)
    log_event(app.participant_name, "initial_questionnaire", "initial_questionnaire_submitted")

    trials = make_trials(app.participant_name)
    save_trial_order(app.participant_name, trials, created_at_utc)

    if not trials:
        messagebox.showerror(
            "No songs found",
            "Add audio files to experiment/stimuli/experiment/, then run the app again.",
        )
        log_event(app.participant_name, "setup", "no_experiment_stimuli_found")
        app.root.destroy()
        return 1

    app.run_practice_phase()
    app.run_main_experiment(trials)
    app.root.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
