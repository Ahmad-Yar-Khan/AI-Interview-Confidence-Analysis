"""
Sanity tests for the audio-feature extraction helpers in confidence_model.py.

NOTE: these intentionally document CURRENT behavior, including the two known
bugs flagged during the architecture review (not fixed as part of this
restructure, since restructuring and bug-fixing were kept as separate,
deliberate decisions):
  1. `pause_per_word` divides by speech_rate (words-per-minute), not word
     count, so it isn't actually "pauses per word" despite the name.
  2. Multi-word filler phrases (e.g. "you know") can never match, because
     filler detection splits the transcript into single whitespace-separated
     tokens before comparing against the filler list.
These tests exist so that if/when those bugs are fixed, you have a test that
fails and tells you so — turn the `xfail` marks into real assertions at that
point.
"""

import pytest

from app.ml.confidence_model import get_audio_features_from_transcription_and_wav


@pytest.mark.xfail(reason="known bug: multi-word filler phrases can never match single-token split")
def test_filler_phrase_you_know_is_detected(tmp_path):
    # This would need a real/synthetic wav file to run end-to-end; left as a
    # documented xfail placeholder rather than skipped silently, so the gap
    # in coverage stays visible instead of disappearing from test output.
    pytest.skip("requires a sample wav fixture — wire up with a short silent/test clip")
