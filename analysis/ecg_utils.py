import numpy as np 
import pandas as pd
import neurokit2 as nk
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def load_ecg_csv(csv_path):
    """
    Load ECG CSV file:
      Polar raw export: polar_timestamp_s, ecg_voltage_uv
    Returns:
      t (np.ndarray), ecg (np.ndarray), df (pd.DataFrame)
    """
    df = pd.read_csv(csv_path)

    if {"polar_timestamp_s", "ecg_voltage_uv"}.issubset(df.columns):
        t = df["polar_timestamp_s"].to_numpy(dtype=float)
        ecg = df["ecg_voltage_uv"].to_numpy(dtype=float)
        return t, ecg, df

    raise ValueError(
        f"Unsupported CSV schema in {csv_path}. "
        f"Found columns: {list(df.columns)}. "
        "Expected either ['time_s', 'ecg'] or "
        "['polar_timestamp_s', 'ecg_voltage_uv']."
    )


def extract_ecg_segment(df_ecg, t_start_unix, t_end_unix):
    """
    Extract ECG samples within a UTC unix time window [t_start, t_end].

    Parameters:
      df_ecg        : DataFrame from load_ecg_csv_utc (must have unix_seconds column)
      t_start_unix  : window start (UTC unix seconds)
      t_end_unix    : window end   (UTC unix seconds)

    Returns:
      ecg (np.ndarray) voltage values, or None if fewer than 3 samples
    """
    mask = (df_ecg["unix_seconds"] >= t_start_unix) & (df_ecg["unix_seconds"] <= t_end_unix)
    seg = df_ecg.loc[mask, "ecg_voltage_uv"].to_numpy(dtype=float)
    return seg if len(seg) >= 3 else None


def compute_rmssd_from_raw(ecg_segment, sampling_rate, min_peaks=4):
    """
    Detect R-peaks in raw ECG segment and compute RMSSD.

    Parameters:
      ecg_segment   : 1-D array of ECG voltages
      sampling_rate : samples per second (Hz)
      min_peaks     : minimum number of R-peaks required (default 4)

    Returns:
      rmssd (float) in milliseconds, or np.nan if not enough peaks
    """
    if ecg_segment is None or len(ecg_segment) < int(sampling_rate * 2):
        return np.nan
    try:
        fs_i = int(np.round(sampling_rate))
        _, peaks_info = nk.ecg_peaks(ecg_segment, sampling_rate=fs_i)
        peaks = peaks_info["ECG_R_Peaks"]
        if len(peaks) < min_peaks:
            return np.nan
        rr_ms = (np.diff(peaks) / sampling_rate) * 1000.0
        return float(np.sqrt(np.mean(np.diff(rr_ms) ** 2)))
    except Exception:
        return np.nan


def compute_sampling_rate(t):
    """
    Compute sampling rate from time array.
    """
    return 1.0 / np.median(np.diff(t))


def get_r_peaks(ecg, sampling_rate):
    """
    Get R-peak indices from ECG signal.
    """
    fs_i = int(np.round(sampling_rate))
    _, peaks_info = nk.ecg_peaks(ecg, sampling_rate=fs_i)
    return peaks_info["ECG_R_Peaks"]


def get_rr_intervals(peaks, t, sampling_rate):
    """
    Get RR intervals from R-peak indices.
    Returns:
      rr_ms (np.ndarray): RR intervals in milliseconds
      rr_t (np.ndarray): R-peak times
    """
    rr_samples = np.diff(peaks)
    rr_ms = (rr_samples / sampling_rate)* 1000.0
    rr_t = t[peaks[1:]]
    return rr_ms, rr_t


def compute_mean_hr(rr_intervals, sampling_rate):
    """
    Compute mean heart rate from RR intervals.
    """
    return f"{60 * sampling_rate / np.mean(rr_intervals):.1f}"


def get_rr_intervals_stats(rr_intervals, verbose=True):
    stats = {
        "Number of RR intervals": len(rr_intervals),
        "Mean RR": np.mean(rr_intervals),
        "Min RR": np.min(rr_intervals),
        "Max RR": np.max(rr_intervals)
    }
    if verbose:
        print("=" * 50)
        print("  RR INTERVALS")
        print("=" * 50)
        for key, value in stats.items():
            print(f"  {key} : {value:.1f} ms")
        print("=" * 50)
    return stats


def compute_rmssd(rr_intervals):
    """
    Compute RMSSD from RR intervals.
    """
    return np.sqrt(np.mean(np.diff(rr_intervals) ** 2))


def get_hrv_metrics(rmssd, rr_intervals, verbose=True):
    value_units = {
        "Mean HR": "bpm",
        "Mean RR": "ms",
        "RMSSD": "ms"
    }
    metrics = {
        "Mean HR": 60_000 / np.mean(rr_intervals),
        "Mean RR": np.mean(rr_intervals),
        "RMSSD": rmssd
    }
    if verbose:
        print("=" * 50)
        print("  HRV METRICS")
        print("=" * 50)
        for key, value in metrics.items():
            print(f"  {key} : {value:.1f} {value_units[key]}")
    return metrics


def plot_raw_ecg(t, ecg):
    """
    Plot the raw ECG so you can visually inspect it.
    """
    fig_raw = go.Figure()
    fig_raw.add_trace(
        go.Scatter(x=t, y=ecg, mode="lines", line=dict(color="#6b8cff", width=0.7), name="Raw ECG")
    )
    fig_raw.update_layout(title="Raw ECG — Clean Recording", xaxis_title="Time (s)", yaxis_title="Amplitude (µV)", template="plotly_dark", height=350)
    fig_raw.show()


def plot_ecg_with_peaks(t, ecg, sampling_rate):
    """
    Plot the ECG with R-peaks marked as red dots — zoomed to the first 20 seconds.
    """
    peaks = get_r_peaks(ecg, sampling_rate)
    t_peaks = t[peaks]
    ecg_peaks = ecg[peaks]

    fig_peaks = go.Figure()
    fig_peaks.add_trace(
        go.Scatter(x=t, y=ecg, mode="lines", line=dict(color="#6b8cff", width=0.7), name="Raw ECG")
    )
    fig_peaks.add_trace(
        go.Scatter(x=t_peaks, y=ecg_peaks, mode="markers",
                   marker=dict(color="#ff4b4b", size=7, symbol="circle"),
                   name="R-peaks")
    )
    fig_peaks.update_layout(
        title="ECG with R-peaks — first 20 s",
        xaxis_title="Time (s)", yaxis_title="Amplitude (µV)",
        xaxis=dict(range=[t[0], t[0] + 20]),
        template="plotly_dark", height=350
    )
    fig_peaks.show()


def plot_ecg_with_rr_intervals(t, ecg, sampling_rate, show_full=False):
    """
    Two stacked subplots:
      - Top: ECG with R-peaks marked, zoomed to the first 20 seconds.
      - Bottom: RR intervals (ms) over time for the same window.
    """
    peaks = get_r_peaks(ecg, sampling_rate)
    rr_ms, rr_t = get_rr_intervals(peaks, t, sampling_rate)

    t_peaks = t[peaks]
    ecg_peaks = ecg[peaks]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("ECG with R-peaks", "RR Intervals")
    )

    fig.add_trace(
        go.Scatter(x=t, y=ecg, mode="lines", line=dict(color="#6b8cff", width=0.7), name="Raw ECG"),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=t_peaks, y=ecg_peaks, mode="markers",
                   marker=dict(color="#ff4b4b", size=7, symbol="circle"),
                   name="R-peaks"),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=rr_t, y=rr_ms, mode="lines+markers",
                   line=dict(color="#ffd166", width=1.5),
                   marker=dict(size=5),
                   name="RR interval"),
        row=2, col=1
    )

    if show_full:
        fig.update_xaxes(range=[t[0], t[-1]])
    else:
        fig.update_xaxes(range=[t[0], t[0] + 20])

    fig.update_yaxes(title_text="Amplitude (µV)", row=1, col=1)
    fig.update_yaxes(title_text="RR (ms)", row=2, col=1)
    fig.update_xaxes(title_text="Time (s)", row=2, col=1)
    fig.update_layout(
        title="ECG with RR intervals — first 20 s",
        template="plotly_dark", height=600
    )
    fig.show()
