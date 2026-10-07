import React, { useState, useEffect, useRef } from "react";
import { CAT_META } from "./ProfileStrip";

export default function InterviewScreen({
  questions,
  currentIndex,
  currentQuestion,
  currentAnswer,
  answeredCount,
  allAnswered,
  progress,
  hasPendingScores,
  loading,
  error,
  onSubmit,
  onNext,
  onPrev,
  onShowReport,
  onClearError,
}) {
  // ttsPhase: idle | speaking | counting | recording | done
  const [ttsPhase,       setTtsPhase]       = useState("idle");
  const [countdown,      setCountdown]      = useState(5);
  const [hasAudio,       setHasAudio]       = useState(false);
  const [replayMap,      setReplayMap]      = useState({});
  const [showEndConfirm, setShowEndConfirm] = useState(false);
  const [waitingForUser, setWaitingForUser] = useState(true);  // "click when ready" gate
  const [isPaused,       setIsPaused]       = useState(false); // distinguishes pause from first-load

  const seqRef          = useRef(0);
  const recognitionRef  = useRef(null);
  const countdownRef    = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef  = useRef([]);
  const audioBlobRef    = useRef(null);
  const wantBlobRef     = useRef(false);
  const elAudioRef      = useRef(null);
  const transcriptRef   = useRef("");

  const isAnswered  = !!currentAnswer;
  const questionId  = currentQuestion?.id;
  const replayCount = questionId ? replayMap[questionId] || 0 : 0;
  const canReplay   = replayCount < 1;

  // ── Sequence control ──────────────────────────────────────

  function stopSequence() {
    wantBlobRef.current = false;
    seqRef.current += 1;
    setHasAudio(false);
    transcriptRef.current = "";
    try { window.speechSynthesis?.cancel(); } catch (_) {}
    if (elAudioRef.current) {
      try { elAudioRef.current.pause(); elAudioRef.current.src = ""; } catch (_) {}
      elAudioRef.current = null;
    }
    clearInterval(countdownRef.current);
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (_) {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current) {
      if (mediaRecorderRef.current.state !== "inactive") {
        try { mediaRecorderRef.current.stop(); } catch (_) {}
      }
      mediaRecorderRef.current = null;
    }
  }

  function runRecording(seq) {
    audioBlobRef.current  = null;
    audioChunksRef.current = [];
    transcriptRef.current  = "";

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) {
      const rec = new SR();
      rec.continuous      = true;
      rec.interimResults  = false;
      rec.lang            = "en-US";
      rec.onresult = (e) => {
        if (seqRef.current !== seq) return;
        for (let i = e.resultIndex; i < e.results.length; i++) {
          if (e.results[i].isFinal) transcriptRef.current += e.results[i][0].transcript + " ";
        }
      };
      rec.onerror = (e) => { if (e.error !== "aborted") console.warn("SR:", e.error); };
      recognitionRef.current = rec;
      rec.start();
    }

    if (navigator.mediaDevices?.getUserMedia) {
      navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
        if (seqRef.current !== seq) { stream.getTracks().forEach(t => t.stop()); return; }
        const mr = new MediaRecorder(stream);
        mr.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
        mr.onstop = () => {
          stream.getTracks().forEach(t => t.stop());
          if (wantBlobRef.current) {
            audioBlobRef.current = new Blob(audioChunksRef.current, { type: mr.mimeType || "audio/webm" });
            wantBlobRef.current = false;
            if (audioChunksRef.current.length > 0) setHasAudio(true);
          }
        };
        mediaRecorderRef.current = mr;
        mr.start();
      }).catch((err) => {
        console.warn("MediaRecorder failed:", err);
        setHasAudio(true);
      });
    } else {
      setHasAudio(true);
    }

    setTtsPhase("recording");
  }

  function runCountdown(seq) {
    setTtsPhase("counting");
    let c = 5;
    setCountdown(c);
    countdownRef.current = setInterval(() => {
      if (seqRef.current !== seq) { clearInterval(countdownRef.current); return; }
      c--;
      setCountdown(c);
      if (c <= 0) { clearInterval(countdownRef.current); if (seqRef.current === seq) runRecording(seq); }
    }, 1000);
  }

  // ┌─────────────────────────────────────────────────────────┐
  // │  TTS PROVIDER — change this one line to switch voices   │
  // │  Options: 'elevenlabs'  |  'browser'                    │
  const TTS_PROVIDER = "elevenlabs"; //│
  // └─────────────────────────────────────────────────────────┘

  async function runTTS_elevenlabs(seq, text) {
    setTtsPhase("speaking");
    try {
      const res  = await fetch("/api/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
      if (!res.ok) throw new Error(`TTS ${res.status}`);
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const audio = new Audio(url);
      elAudioRef.current = audio;
      audio.onended = () => { URL.revokeObjectURL(url); elAudioRef.current = null; if (seqRef.current === seq) runCountdown(seq); };
      audio.onerror = () => { URL.revokeObjectURL(url); elAudioRef.current = null; if (seqRef.current === seq) runCountdown(seq); };
      await audio.play();
    } catch (e) {
      console.error("ElevenLabs TTS error:", e);
      if (seqRef.current === seq) runCountdown(seq);
    }
  }

  function _pickBrowserVoice() {
    const voices = window.speechSynthesis.getVoices();
    const tiers = [
      (v) => /microsoft.*natural/i.test(v.name) && /en[-_]us/i.test(v.lang),
      (v) => /microsoft/i.test(v.name) && /online/i.test(v.name) && /en/i.test(v.lang),
      (v) => /microsoft.*(aria|jenny|guy|davis)/i.test(v.name),
      (v) => /google/i.test(v.name) && /en[-_]us/i.test(v.lang),
      (v) => /en[-_]us/i.test(v.lang),
      (v) => /en/i.test(v.lang),
    ];
    for (const test of tiers) { const m = voices.find(test); if (m) return m; }
    return null;
  }

  function runTTS_browser(seq, text) {
    setTtsPhase("speaking");
    if (!window.speechSynthesis) { runCountdown(seq); return; }
    window.speechSynthesis.cancel();
    const speak = () => {
      const utter = new SpeechSynthesisUtterance(text);
      const voice = _pickBrowserVoice();
      if (voice) utter.voice = voice;
      utter.rate = 0.88; utter.pitch = 1.0; utter.volume = 1.0;
      utter.onend   = () => { if (seqRef.current === seq) runCountdown(seq); };
      utter.onerror = () => { if (seqRef.current === seq) runCountdown(seq); };
      window.speechSynthesis.speak(utter);
    };
    if (window.speechSynthesis.getVoices().length > 0) {
      speak();
    } else {
      window.speechSynthesis.onvoiceschanged = () => { window.speechSynthesis.onvoiceschanged = null; speak(); };
    }
  }

  function runTTS(seq, text) {
    if (TTS_PROVIDER === "elevenlabs") return runTTS_elevenlabs(seq, text);
    return runTTS_browser(seq, text);
  }

  // ── Effects ───────────────────────────────────────────────

  useEffect(() => {
    stopSequence();
    setIsPaused(false);
    const seq = seqRef.current;
    audioBlobRef.current  = null;
    audioChunksRef.current = [];

    if (!currentQuestion || isAnswered) {
      setTtsPhase("idle");
      setWaitingForUser(false);
      return;
    }

    if (currentIndex === 0) {
      // First question: always show the "ready" gate before auto-firing TTS
      setWaitingForUser(true);
      setTtsPhase("idle");
    } else {
      // Subsequent questions: auto-start
      setWaitingForUser(false);
      runTTS(seq, currentQuestion.question);
    }
  }, [currentIndex, isAnswered]); // eslint-disable-line

  useEffect(() => () => stopSequence(), []); // eslint-disable-line

  // ── Handlers ──────────────────────────────────────────────

  const handleReady = () => {
    setWaitingForUser(false);
    setIsPaused(false);
    const seq = seqRef.current;
    runTTS(seq, currentQuestion.question);
  };

  const handlePause = () => {
    stopSequence();
    setIsPaused(true);
    setWaitingForUser(true);
    setTtsPhase("idle");
  };

  const handleReplay = () => {
    if (!canReplay || !currentQuestion) return;
    setReplayMap(prev => ({ ...prev, [questionId]: (prev[questionId] || 0) + 1 }));
    stopSequence();
    const seq = seqRef.current;
    runTTS(seq, currentQuestion.question);
  };

  const handleStopRecording = () => {
    stopSequence();
    wantBlobRef.current = true;
    setTtsPhase("done");
  };

  const handleSubmit = () => {
    if (!hasAudio || loading) return;
    const text = transcriptRef.current.trim() || "[voice response]";
    onSubmit(text, replayCount, audioBlobRef.current);
  };

  // ── Render ────────────────────────────────────────────────

  if (!currentQuestion) return null;

  const q          = currentQuestion;
  const isHR       = !q.has_answer;
  const catMeta    = CAT_META[q.category] || { color: "#6b7794", label: q.category };

  const isSpeaking  = ttsPhase === "speaking";
  const isCounting  = ttsPhase === "counting";
  const isRecording = ttsPhase === "recording";
  const isDone      = ttsPhase === "done";
  const showReplay  = (isSpeaking || isCounting) && canReplay && !isAnswered;
  const showPause   = (isSpeaking || isCounting || isRecording) && !isAnswered;

  return (
    <div className="interview-room">
      <style>{`
        @keyframes si-wave {
          0%, 100% { transform: scaleY(0.35); }
          50%       { transform: scaleY(1); }
        }
        @keyframes si-pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.4; transform: scale(1.4); }
        }
        @keyframes si-pop {
          from { transform: scale(1.25); opacity: 0.4; }
          to   { transform: scale(1);    opacity: 1; }
        }
      `}</style>

      {/* ── Minimal focus bar ──────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 24px', height: 48,
        background: 'var(--surface)', borderBottom: '1px solid var(--border)',
        flexShrink: 0,
      }}>
        <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1rem', letterSpacing: '-0.02em', color: 'var(--text2)' }}>
          Smart<span style={{ color: 'var(--accent)' }}>Interview</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {hasPendingScores && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.72rem', color: 'var(--muted)' }}>
              <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
              Scoring…
            </div>
          )}
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: '0.68rem',
            color: 'var(--text2)', background: 'var(--surface2)',
            border: '1px solid var(--border2)',
            borderRadius: 'var(--radius-pill)', padding: '3px 10px',
          }}>
            {answeredCount} / {questions.length} answered
          </span>
        </div>
      </div>

      {/* ── Main content ───────────────────────────────────── */}
      <div style={{ flex: 1, maxWidth: 820, width: '100%', margin: '0 auto', padding: '28px 24px' }}>

        {/* Progress */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ fontSize: "0.78rem", color: "var(--text2)" }}>
              Question {currentIndex + 1} of {questions.length}
            </span>
            <span style={{ fontSize: "0.78rem", color: "var(--text2)" }}>
              {Math.round(progress)}% complete
            </span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <div style={{ display: "flex", gap: 5, marginTop: 10, flexWrap: "wrap" }}>
            {questions.map((_, i) => (
              <div key={i} style={{
                width: 8, height: 8, borderRadius: "50%",
                background: i === currentIndex ? "var(--accent)" : "var(--border2)",
                transition: "background 0.2s",
              }} />
            ))}
          </div>
        </div>

        {/* Question card */}
        <div className="card fade-in" style={{ marginBottom: 0 }}>

          {/* Meta row */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.7rem", color: "var(--muted)" }}>
              Q{String(currentIndex + 1).padStart(2, "0")}
            </span>
            <span style={{
              fontFamily: "var(--font-mono)", fontSize: "0.68rem",
              padding: "2px 10px", borderRadius: "var(--radius-pill)",
              border: `1px solid ${catMeta.color}`, color: catMeta.color,
              background: `${catMeta.color}14`,
            }}>
              {catMeta.label}
            </span>
            <span className={`diff-badge diff-${q.difficulty}`}>{q.difficulty}</span>
            {isHR && (
              <span style={{
                fontFamily: "var(--font-mono)", fontSize: "0.65rem",
                padding: "2px 9px", borderRadius: "var(--radius-pill)",
                background: "rgba(148,163,184,0.10)", border: "1px solid rgba(148,163,184,0.2)",
                color: "var(--text2)",
              }}>
                Open-ended
              </span>
            )}
          </div>

          {/* Why */}
          {q.why && (
            <div style={{
              display: "flex", alignItems: "flex-start", gap: 8,
              background: "var(--surface2)", borderRadius: 8,
              padding: "8px 12px", marginBottom: 14,
              fontSize: "0.75rem", color: "var(--text2)",
            }}>
              <span style={{ fontSize: "0.85rem", flexShrink: 0 }}>💡</span>
              <span>{q.why}</span>
            </div>
          )}

          {/* Question text */}
          <div style={{ fontSize: "1.05rem", fontWeight: 500, lineHeight: 1.6, marginBottom: 20, color: "var(--text)" }}>
            {q.question}
          </div>

          {/* HR guidance */}
          {isHR && !isAnswered && (
            <div style={{
              background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.15)",
              borderRadius: 8, padding: "10px 14px", marginBottom: 16,
              fontSize: "0.8rem", color: "var(--text2)", lineHeight: 1.55,
            }}>
              <strong style={{ color: "var(--text)" }}>Behavioral question —</strong>{" "}
              use the <strong style={{ color: "var(--text)" }}>STAR method</strong>:
              describe the <em>Situation</em>, your <em>Task</em>, the <em>Action</em> you took,
              and the <em>Result</em> achieved. Aim for 100–200 words.
            </div>
          )}

          {/* ── Voice interface ── */}
          {!isAnswered && (
            <div>

              {/* READY GATE — first question or after pause */}
              {waitingForUser && (
                <div style={{
                  display: "flex", flexDirection: "column", alignItems: "center",
                  padding: "36px 0 28px", gap: 16,
                }}>
                  <div style={{
                    width: 64, height: 64, borderRadius: "50%",
                    border: "2px solid var(--accent)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: "1.6rem",
                  }}>
                    {isPaused ? "⏸" : "🎙"}
                  </div>
                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontWeight: 600, fontSize: "0.96rem", marginBottom: 4 }}>
                      {isPaused ? "Interview paused" : "Ready to begin?"}
                    </div>
                    <div style={{ fontSize: "0.8rem", color: "var(--text2)" }}>
                      {isPaused
                        ? "Click below when you're ready to continue with this question."
                        : "The question will be read aloud. Recording starts automatically after."}
                    </div>
                  </div>
                  <button
                    className="btn btn-primary"
                    style={{ fontSize: "0.9rem", padding: "10px 28px" }}
                    onClick={handleReady}
                  >
                    {isPaused ? "▶ Resume Interview" : "▶ Click when ready"}
                  </button>
                </div>
              )}

              {/* SPEAKING phase */}
              {!waitingForUser && isSpeaking && (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "32px 0 24px", gap: 14 }}>
                  <div style={{ display: "flex", gap: 4, alignItems: "center", height: 40 }}>
                    {[0.35, 0.6, 1, 0.75, 0.45, 0.85, 0.55, 0.9, 0.4, 0.65].map((h, i) => (
                      <div key={i} style={{
                        width: 4, borderRadius: 2, background: "var(--accent)",
                        height: `${h * 100}%`,
                        animation: `si-wave ${0.7 + i * 0.06}s ease-in-out infinite`,
                        animationDelay: `${i * 0.07}s`,
                      }} />
                    ))}
                  </div>
                  <span style={{ fontSize: "0.84rem", color: "var(--text2)" }}>Reading question aloud…</span>
                  <div style={{ display: "flex", gap: 8 }}>
                    {showReplay && (
                      <button className="btn btn-ghost" onClick={handleReplay} style={{ fontSize: "0.78rem" }}>
                        ↺ Replay
                      </button>
                    )}
                    {showPause && (
                      <button className="btn btn-ghost" onClick={handlePause} style={{ fontSize: "0.78rem" }}>
                        ⏸ Pause
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* COUNTING phase */}
              {!waitingForUser && isCounting && (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "28px 0 20px", gap: 12 }}>
                  <div key={countdown} style={{
                    width: 72, height: 72, borderRadius: "50%",
                    border: "2px solid var(--accent)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: "2rem", fontWeight: 700, color: "var(--accent)",
                    animation: "si-pop 0.25s ease-out forwards",
                  }}>
                    {countdown}
                  </div>
                  <span style={{ fontSize: "0.84rem", color: "var(--text2)" }}>
                    Recording starts in {countdown}s — prepare your answer
                  </span>
                  <div style={{ display: "flex", gap: 8 }}>
                    {showReplay && (
                      <button className="btn btn-ghost" onClick={handleReplay} style={{ fontSize: "0.78rem" }}>
                        ↺ Replay
                      </button>
                    )}
                    {showPause && (
                      <button className="btn btn-ghost" onClick={handlePause} style={{ fontSize: "0.78rem" }}>
                        ⏸ Pause
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* RECORDING phase — waveform in red */}
              {isRecording && (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "36px 0 28px", gap: 16 }}>
                  <div style={{ display: "flex", gap: 4, alignItems: "center", height: 40 }}>
                    {[0.45, 0.8, 0.6, 1, 0.5, 0.9, 0.7, 0.55, 0.85, 0.65].map((h, i) => (
                      <div key={i} style={{
                        width: 4, borderRadius: 2, background: "var(--red)",
                        height: `${h * 100}%`,
                        animation: `si-wave ${0.65 + i * 0.06}s ease-in-out infinite`,
                        animationDelay: `${i * 0.07}s`,
                      }} />
                    ))}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div className="mic-glow" style={{
                      width: 10, height: 10, borderRadius: "50%",
                      background: "var(--red)",
                    }} />
                    <span style={{ fontSize: "0.9rem", color: "var(--red)", fontWeight: 600 }}>Recording</span>
                    <span style={{ fontSize: "0.82rem", color: "var(--muted)" }}>— speak your answer clearly</span>
                  </div>
                  <div style={{ display: "flex", gap: 10 }}>
                    <button
                      onClick={handleStopRecording}
                      style={{
                        padding: "9px 22px", borderRadius: "var(--radius-sm)",
                        background: "rgba(251,113,133,0.10)", border: "1px solid rgba(251,113,133,0.3)",
                        color: "var(--red)", cursor: "pointer", fontSize: "0.84rem", fontWeight: 500,
                      }}
                    >
                      ■ Stop Recording
                    </button>
                    <button className="btn btn-ghost" onClick={handlePause} style={{ fontSize: "0.84rem" }}>
                      ⏸ Pause
                    </button>
                  </div>
                </div>
              )}

              {/* DONE phase */}
              {isDone && (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "28px 0 20px", gap: 14 }}>
                  {hasAudio ? (
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: "1.1rem", color: "var(--green)" }}>✓</span>
                      <span style={{ fontSize: "0.88rem", color: "var(--text2)" }}>Answer recorded — ready to submit</span>
                    </div>
                  ) : (
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                      <span style={{ fontSize: "0.84rem", color: "var(--muted)" }}>Saving audio…</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Already answered */}
          {isAnswered && (
            <div style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "12px 16px",
              background: "rgba(52,211,153,0.06)", border: "1px solid rgba(52,211,153,0.2)",
              borderRadius: "var(--radius-sm)",
            }}>
              <span style={{ fontSize: "1rem", color: "var(--green)" }}>✓</span>
              <span style={{ fontSize: "0.84rem", color: "var(--text2)" }}>Answer submitted</span>
            </div>
          )}

          {/* Error */}
          {error && (
            <div style={{
              marginTop: 12, background: "rgba(251,113,133,0.08)",
              border: "1px solid rgba(251,113,133,0.2)",
              borderRadius: 8, padding: "10px 14px",
              color: "var(--red)", fontSize: "0.82rem",
            }}>
              ⚠ {error}
              <button onClick={onClearError} style={{ marginLeft: 8, background: "none", border: "none", cursor: "pointer", color: "var(--red)", fontSize: "0.8rem" }}>✕</button>
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 16 }}>
              <div className="spinner" style={{ width: 20, height: 20, borderWidth: 2 }} />
              <span style={{ fontSize: "0.82rem", color: "var(--text2)" }}>Please wait…</span>
            </div>
          )}

          {/* Navigation */}
          <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            marginTop: 24, paddingTop: 18, borderTop: "1px solid var(--border)",
          }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button className="btn btn-ghost" onClick={onPrev} disabled={currentIndex === 0} style={{ minWidth: 90 }}>
                ← Prev
              </button>
              {answeredCount > 0 && (
                <button
                  onClick={() => !isRecording && setShowEndConfirm(true)}
                  disabled={isRecording}
                  style={{
                    padding: "6px 14px", borderRadius: "var(--radius-sm)",
                    background: isRecording ? "transparent" : "rgba(251,113,133,0.08)",
                    border: `1px solid ${isRecording ? "var(--border2)" : "rgba(251,113,133,0.25)"}`,
                    color: isRecording ? "var(--muted)" : "#f87171",
                    cursor: isRecording ? "not-allowed" : "pointer",
                    fontSize: "0.78rem", fontWeight: 500,
                    opacity: isRecording ? 0.45 : 1, transition: "all 0.2s",
                  }}
                >
                  End Interview
                </button>
              )}
            </div>

            <div style={{ display: "flex", gap: 10 }}>
              {isDone && !isAnswered && (
                <button className="btn btn-primary" onClick={handleSubmit} disabled={!hasAudio || loading}>
                  {loading ? "Saving…" : "Submit Answer"}
                </button>
              )}
              {isAnswered && currentIndex < questions.length - 1 && (
                <button className="btn btn-primary" onClick={onNext}>Next →</button>
              )}
              {isAnswered && currentIndex === questions.length - 1 && (
                <button className="btn btn-green" onClick={onShowReport} disabled={hasPendingScores} title={hasPendingScores ? "Scoring in progress…" : undefined}>
                  {hasPendingScores ? "Scoring…" : "View Report →"}
                </button>
              )}
              {!isAnswered && allAnswered && (
                <button className="btn btn-green" onClick={onShowReport} disabled={hasPendingScores} title={hasPendingScores ? "Scoring in progress…" : undefined}>
                  {hasPendingScores ? "Scoring…" : "View Report →"}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── End Interview confirmation modal ── */}
      {showEndConfirm && (
        <div
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)", backdropFilter: "blur(4px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}
          onClick={() => setShowEndConfirm(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "28px 32px", maxWidth: 460, width: "90%", boxShadow: "0 24px 48px rgba(0,0,0,0.4)" }}
          >
            <div style={{ fontSize: "1.05rem", fontWeight: 600, marginBottom: 12 }}>End interview early?</div>
            <div style={{
              background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.25)",
              borderRadius: 8, padding: "12px 14px", fontSize: "0.82rem",
              color: "var(--text2)", lineHeight: 1.6, marginBottom: 18,
            }}>
              <div style={{ fontWeight: 600, color: "#fbbf24", marginBottom: 6 }}>⚠ What happens next</div>
              <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 5 }}>
                <li>You have answered <strong style={{ color: "var(--text)" }}>{answeredCount}</strong> of <strong style={{ color: "var(--text)" }}>{questions.length}</strong> questions.</li>
                <li>The remaining <strong style={{ color: "var(--text)" }}>{questions.length - answeredCount}</strong> question{questions.length - answeredCount !== 1 ? "s" : ""} will be skipped.</li>
                <li>Your report will be calculated from completed answers only.</li>
                <li>Any pending confidence analyses will still finish.</li>
              </ul>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <button className="btn btn-ghost" onClick={() => setShowEndConfirm(false)}>Cancel</button>
              <button
                onClick={() => { setShowEndConfirm(false); onShowReport(); }}
                disabled={hasPendingScores}
                style={{
                  padding: "7px 18px", borderRadius: "var(--radius-sm)",
                  background: hasPendingScores ? "rgba(251,113,133,0.05)" : "rgba(251,113,133,0.12)",
                  border: "1px solid rgba(251,113,133,0.35)",
                  color: hasPendingScores ? "rgba(251,113,133,0.45)" : "#f87171",
                  cursor: hasPendingScores ? "not-allowed" : "pointer",
                  fontSize: "0.84rem", fontWeight: 600,
                }}
              >
                {hasPendingScores ? "Scoring…" : "Yes, end interview"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
