#!/usr/bin/env python

import os
import pandas as pd
import numpy as np
import joblib
from faster_whisper import WhisperModel
import tempfile
import shutil
from pydub import AudioSegment
from pydub.silence import detect_silence

# Inject ffmpeg bin dir into PATH so pydub's which("ffprobe") finds it at runtime.
# Also set AudioSegment.converter for the ffmpeg executable.
_FFMPEG_BIN = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
)
if os.path.isdir(_FFMPEG_BIN):
    os.environ["PATH"] = _FFMPEG_BIN + os.pathsep + os.environ.get("PATH", "")
    AudioSegment.converter = os.path.join(_FFMPEG_BIN, "ffmpeg.exe")
from sklearn.pipeline import Pipeline # Required for type hinting and joblib loading
from sklearn.ensemble import VotingClassifier # Required for joblib loading
# Ensure all scikit-learn, xgboost, and other classes used in pipelines are imported if they are not part of the standard Python library
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
import xgboost as xgb

from app.core.config import settings

# --- Configuration --- #
# Resolved centrally in app/core/config.py (relative to BACKEND_ROOT, not this
# file's own directory — this module moved from backend/feature_extractor.py
# to backend/app/ml/confidence_model.py during the restructure, so a path
# computed from __file__ here would no longer point at backend/models/).
MODEL_PATH = settings.CONFIDENCE_MODEL_PATH
FEATURES_LIST_PATH = settings.CONFIDENCE_FEATURES_PATH

# --- Helper Functions (copied from Colab notebook) --- #

def get_audio_features_from_transcription_and_wav(
    wav_file_path: str,
    transcription: str,
    audio_duration_seconds: float
) -> dict:
    """
    Extracts relevant audio features from a WAV file using transcription for
    filler words, speech rate, and repeated words, and pydub for pauses.

    Args:
        wav_file_path (str): The path to the (temporary) WAV audio file.
        transcription (str): The text transcription of the audio.
        audio_duration_seconds (float): The total duration of the audio in seconds.

    Returns:
        dict: A dictionary of extracted features, ready for prediction.
    """
    if not os.path.exists(wav_file_path):
        raise FileNotFoundError(f"Audio file not found: {wav_file_path}")

    audio = AudioSegment.from_wav(wav_file_path)

    # --- Feature extraction from transcription ---
    words = transcription.lower().split()
    word_count = len(words)

    # Simple Filler words detection
    filler_words_list = ['um', 'uh', 'like', 'you know', 'so', 'basically', 'actually', 'literally']
    filler_words_count = sum(1 for word in words if word in filler_words_list)

    # Speech rate calculation (words per minute)
    speech_rate = (word_count / audio_duration_seconds) * 60 if audio_duration_seconds > 0 else 0.0

    # Repeated words detection (simple consecutive repetition)
    total_repeated_words = 0
    for i in range(len(words) - 1):
        if words[i] == words[i+1]:
            total_repeated_words += 1

    # --- Pause detection using pydub ---
    # Adjust silence_thresh to be relative to the audio's average loudness
    silence_threshold_db = audio.dBFS - 10
    silences = detect_silence(audio, min_silence_len=500, silence_thresh=silence_threshold_db)

    total_pauses = len(silences)
    average_pause_duration = 0.0
    if total_pauses > 0:
        total_pause_duration_ms = sum([s[1] - s[0] for s in silences])
        average_pause_duration = total_pause_duration_ms / total_pauses / 1000.0 # convert to seconds

    # Calculate pause_per_word
    pause_per_word = total_pauses / speech_rate if speech_rate > 0 else 0.0

    features = {
        "filler_words": filler_words_count,
        "speech_rate": speech_rate,
        "total_repeated_words": total_repeated_words,
        "total_pauses": total_pauses,
        "average_pause_duration": average_pause_duration,
        "pause_per_word": pause_per_word
    }
    return features

def predict_confidence_score(
    features_dict: dict,
    model: Pipeline,
    feature_names: list
) -> dict:
    """
    Predicts the confidence score for a new audio recording given its extracted features.

    Args:
        features_dict (dict): A dictionary where keys are feature names and values are their corresponding numeric values.
        model (Pipeline): The trained scikit-learn pipeline (or VotingClassifier).
        feature_names (list): A list of feature names in the correct order as used during training.

    Returns:
        dict: A dictionary containing the predicted label, confidence probability, and a 1-10 confidence score.
    """
    # Create a DataFrame from the input features_dict
    # It's important to match the column order used during training
    input_df = pd.DataFrame([features_dict], columns=feature_names)

    # Predict probability (P(Confident=1))
    proba = model.predict_proba(input_df)[:, 1][0]

    # Predict the label
    label = "Confident" if proba >= 0.5 else "Unconfident"

    # Convert probability to 1-10 confidence score
    confidence_score_1_to_10 = 1 + 9 * proba

    return {
        "predicted_label": label,
        "confidence_probability": proba,
        "confidence_score_1_to_10": confidence_score_1_to_10
    }

# --- Main Prediction Function for VS Code --- #

# Lazily loaded on first use
_WHISPER_MODEL = None

def _get_whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        # Upgraded from Whisper small to Faster-Whisper medium.en for:
        # - significantly improved transcription accuracy
        # - better handling of technical vocabulary (ML, APIs, system design terms)
        # - improved robustness for interview-style conversational speech
        # - lower latency inference compared to original Whisper implementation
        print("Loading Faster-Whisper medium.en model...")
        for device, compute_type in [("cuda", "float16"), ("cuda", "int8"), ("cpu", "int8")]:
            try:
                _WHISPER_MODEL = WhisperModel("medium.en", device=device, compute_type=compute_type)
                print(f"Faster-Whisper loaded: device={device}, compute_type={compute_type}")
                break
            except Exception as e:
                print(f"  [{device}/{compute_type}] failed: {e} — trying fallback...")
        if _WHISPER_MODEL is None:
            raise RuntimeError("Failed to initialize Faster-Whisper on any device/compute_type.")
    return _WHISPER_MODEL

def predict_confidence_for_audio_vscode(audio_file_path: str) -> dict:
    """
    Predicts confidence scores for a given audio file (m4a, mp3, or wav) using
    Whisper for transcription and the loaded ensemble model.

    Args:
        audio_file_path (str): The path to the audio file (m4a, mp3, or wav).

    Returns:
        dict: A dictionary containing the prediction results.
    """
    print(f"Processing audio file: {audio_file_path}")

    if not os.path.exists(audio_file_path):
        print(f"Error: Audio file not found at {audio_file_path}")
        return {}

    temp_dir = tempfile.mkdtemp()
    temp_wav_path = os.path.join(temp_dir, "temp_audio.wav")

    try:
        # Step 1: Convert to WAV if necessary (pydub handles various formats)
        audio = AudioSegment.from_file(audio_file_path)
        audio.export(temp_wav_path, format="wav")
        audio_duration_seconds = len(audio) / 1000.0

        # Step 2: Transcribe with Faster-Whisper
        print("Transcribing audio with Faster-Whisper...")
        segments_gen, _ = _get_whisper_model().transcribe(temp_wav_path, beam_size=5)
        segments = [{"start": seg.start, "end": seg.end, "text": seg.text.strip()} for seg in segments_gen]
        transcription = " ".join(seg["text"] for seg in segments)
        print(f"Transcription: \"{transcription}\"")

        # Step 3: Extract features
        extracted_features = get_audio_features_from_transcription_and_wav(
            wav_file_path=temp_wav_path,
            transcription=transcription,
            audio_duration_seconds=audio_duration_seconds
        )

        print("\nAutomatically Extracted Features:")
        for k, v in extracted_features.items():
            print(f"  {k}: {v:.2f}" if isinstance(v, float) else f"  {k}: {v}")

        # Step 4: Load the model and feature names
        # These are loaded here to make the function self-contained
        # but in a real application, you might load them once at startup.
        try:
            ensemble_model = joblib.load(MODEL_PATH)
            feature_names = joblib.load(FEATURES_LIST_PATH)
        except FileNotFoundError:
            print(f"Error: Model or feature list not found. Ensure '{MODEL_PATH}' and '{FEATURES_LIST_PATH}' exist.")
            return {}
        except Exception as e:
            print(f"Error loading model or feature list: {e}")
            return {}

        # Step 5: Predict confidence
        prediction = predict_confidence_score(
            features_dict=extracted_features,
            model=ensemble_model,
            feature_names=feature_names
        )

        print("\n--- Prediction Results ---")
        print(f"  Predicted Label: {prediction['predicted_label']}")
        print(f"  Confidence Probability (P(Confident)): {prediction['confidence_probability']:.2f}")
        print(f"  Confidence Score (1-10): {prediction['confidence_score_1_to_10']:.1f}")
        
        return {**prediction, "transcript": transcription}

    except Exception as e:
        print(f"An unexpected error occurred during prediction: {e}")
        return {}
    finally:
        # Clean up the temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"Cleaned up temporary directory: {temp_dir}")

# --- Example Usage (only runs when the script is executed directly) --- #
if __name__ == "__main__":
    # IMPORTANT: Change this to the actual path of an audio file on your system.
    AUDIO_FILE_TO_PREDICT = '/content/drive/MyDrive/Confidence_Analysis_vms/Test Data/Confident.m4a'

    if os.path.exists(AUDIO_FILE_TO_PREDICT):
        results = predict_confidence_for_audio_vscode(AUDIO_FILE_TO_PREDICT)
        if results:
            print("\nFinal Prediction Results:")
            print(f"  Predicted Label: {results['predicted_label']}")
            print(f"  Confidence Score (1-10): {results['confidence_score_1_to_10']:.1f}")
    else:
        print(f"Error: The example audio file '{AUDIO_FILE_TO_PREDICT}' was not found.")
        print("Please update AUDIO_FILE_TO_PREDICT to a valid path on your system.")
        print("Also, ensure MODEL_PATH and FEATURES_LIST_PATH at the top of this script are correct.")
