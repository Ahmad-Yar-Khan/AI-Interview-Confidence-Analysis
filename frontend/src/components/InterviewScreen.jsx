import React, { useState, useEffect, useRef } from 'react'
import ScoreBlock from './ScoreBlock'
import { CAT_META } from './ProfileStrip'

export default function InterviewScreen({
  questions,
  currentIndex,
  currentQuestion,
  currentAnswer,
  answeredCount,
  allAnswered,
  progress,
  loading,
  error,
  onSubmit,
  onNext,
  onPrev,
  onShowReport,
  onClearError,
}) {
  // ttsPhase: idle | speaking | counting | recording | done
  const [ttsPhase,     setTtsPhase]     = useState('idle')
  const [countdown,    setCountdown]    = useState(5)
  const [transcript,   setTranscript]   = useState('')
  const [interimText,  setInterimText]  = useState('')
  const [replayMap,    setReplayMap]    = useState({})   // { [qId]: count }

  const seqRef          = useRef(0)
  const recognitionRef  = useRef(null)
  const countdownRef    = useRef(null)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef   = useRef([])
  const audioBlobRef     = useRef(null)
  const wantBlobRef      = useRef(false)  // true only when manually stopping to submit

  const isAnswered  = !!currentAnswer
  const questionId  = currentQuestion?.id
  const replayCount = questionId ? (replayMap[questionId] || 0) : 0
  const canReplay   = replayCount < 1

  // ── Sequence control ──────────────────────────────────────

  function stopSequence() {
    wantBlobRef.current = false
    seqRef.current += 1
    try { window.speechSynthesis?.cancel() } catch (_) {}
    clearInterval(countdownRef.current)
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch (_) {}
      recognitionRef.current = null
    }
    if (mediaRecorderRef.current) {
      if (mediaRecorderRef.current.state !== 'inactive') {
        try { mediaRecorderRef.current.stop() } catch (_) {}
      }
      mediaRecorderRef.current = null
    }
  }

  function runRecording(seq) {
    // Reset audio capture state for this session
    audioBlobRef.current   = null
    audioChunksRef.current = []

    // ── SpeechRecognition for live transcript ─────────────
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SR) {
      const rec = new SR()
      rec.continuous     = true
      rec.interimResults = true
      rec.lang           = 'en-US'

      let final = ''
      rec.onresult = (e) => {
        if (seqRef.current !== seq) return
        let interim = ''
        for (let i = e.resultIndex; i < e.results.length; i++) {
          if (e.results[i].isFinal) {
            final += e.results[i][0].transcript + ' '
          } else {
            interim += e.results[i][0].transcript
          }
        }
        setTranscript(final)
        setInterimText(interim)
      }
      rec.onerror = (e) => {
        if (e.error !== 'aborted') console.warn('SR:', e.error)
      }

      recognitionRef.current = rec
      rec.start()
    }

    // ── MediaRecorder for audio capture (confidence analysis) ─
    if (navigator.mediaDevices?.getUserMedia) {
      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
          if (seqRef.current !== seq) { stream.getTracks().forEach(t => t.stop()); return }
          const mr = new MediaRecorder(stream)
          mr.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunksRef.current.push(e.data)
          }
          mr.onstop = () => {
            stream.getTracks().forEach(t => t.stop())
            if (wantBlobRef.current) {
              audioBlobRef.current = new Blob(
                audioChunksRef.current,
                { type: mr.mimeType || 'audio/webm' },
              )
              wantBlobRef.current = false
            }
          }
          mediaRecorderRef.current = mr
          mr.start()
        })
        .catch(err => console.warn('MediaRecorder failed to start:', err))
    }

    setTtsPhase('recording')
  }

  function runCountdown(seq) {
    setTtsPhase('counting')
    let c = 5
    setCountdown(c)
    countdownRef.current = setInterval(() => {
      if (seqRef.current !== seq) { clearInterval(countdownRef.current); return }
      c--
      setCountdown(c)
      if (c <= 0) {
        clearInterval(countdownRef.current)
        if (seqRef.current === seq) runRecording(seq)
      }
    }, 1000)
  }

  function runTTS(seq, text) {
    setTtsPhase('speaking')
    if (!window.speechSynthesis) { runCountdown(seq); return }
    window.speechSynthesis.cancel()
    const utter = new SpeechSynthesisUtterance(text)
    utter.rate  = 0.9
    utter.pitch = 1
    utter.onend = () => {
      if (seqRef.current === seq) runCountdown(seq)
    }
    window.speechSynthesis.speak(utter)
  }

  // ── Effects ───────────────────────────────────────────────

  useEffect(() => {
    stopSequence()
    const seq = seqRef.current
    audioBlobRef.current   = null
    audioChunksRef.current = []

    if (!currentQuestion || isAnswered) {
      setTtsPhase('idle')
      return
    }

    setTranscript('')
    setInterimText('')
    runTTS(seq, currentQuestion.question)
  }, [currentIndex, isAnswered])  // eslint-disable-line

  // Cleanup on unmount
  useEffect(() => () => stopSequence(), [])  // eslint-disable-line

  // ── Handlers ──────────────────────────────────────────────

  const handleReplay = () => {
    if (!canReplay || !currentQuestion) return
    setReplayMap(prev => ({ ...prev, [questionId]: (prev[questionId] || 0) + 1 }))
    stopSequence()
    const seq = seqRef.current
    setTranscript('')
    setInterimText('')
    runTTS(seq, currentQuestion.question)
  }

  const handleStopRecording = () => {
    stopSequence()          // zeroes wantBlobRef, stops MR (async onstop pending)
    wantBlobRef.current = true  // onstop fires after this sync block → sees true → saves blob
    setInterimText('')
    setTtsPhase('done')
  }

  const handleSubmit = () => {
    if (!transcript.trim() || loading) return
    onSubmit(transcript.trim(), replayCount, audioBlobRef.current)
  }

  // ── Derived render flags ──────────────────────────────────

  if (!currentQuestion) return null

  const q       = currentQuestion
  const isHR    = !q.has_answer
  const catMeta = CAT_META[q.category] || { color: '#6b7794', label: q.category }

  const isSpeaking  = ttsPhase === 'speaking'
  const isCounting  = ttsPhase === 'counting'
  const isRecording = ttsPhase === 'recording'
  const isDone      = ttsPhase === 'done'
  const showReplay  = (isSpeaking || isCounting) && canReplay && !isAnswered

  return (
    <div style={{ maxWidth: 820, margin: '0 auto', padding: '28px 24px' }}>

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

      {/* Progress bar */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: '0.78rem', color: 'var(--text2)' }}>
            Question {currentIndex + 1} of {questions.length}
          </span>
          <span style={{ fontSize: '0.78rem', color: 'var(--text2)' }}>
            {answeredCount} answered · {Math.round(progress)}% complete
          </span>
        </div>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <div style={{ display: 'flex', gap: 5, marginTop: 10, flexWrap: 'wrap' }}>
          {questions.map((_, i) => (
            <div key={i} title={`Q${i + 1}`} style={{
              width: 8, height: 8, borderRadius: '50%',
              background: i === currentIndex ? 'var(--accent)' : 'var(--border2)',
              transition: 'background 0.2s',
            }} />
          ))}
        </div>
      </div>

      {/* Question card */}
      <div className="card fade-in" style={{ marginBottom: 0 }}>

        {/* Meta row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--muted)' }}>
            Q{String(currentIndex + 1).padStart(2, '0')}
          </span>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: '0.68rem',
            padding: '2px 10px', borderRadius: 'var(--radius-pill)',
            border: `1px solid ${catMeta.color}`,
            color: catMeta.color,
            background: `${catMeta.color}14`,
          }}>
            {catMeta.label}
          </span>
          <span className={`diff-badge diff-${q.difficulty}`}>{q.difficulty}</span>
          {isHR && (
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: '0.65rem',
              padding: '2px 9px', borderRadius: 'var(--radius-pill)',
              background: 'rgba(148,163,184,0.10)',
              border: '1px solid rgba(148,163,184,0.2)',
              color: 'var(--text2)',
            }}>
              Open-ended
            </span>
          )}
        </div>

        {/* Why this question */}
        {q.why && (
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: 8,
            background: 'var(--surface2)', borderRadius: 8,
            padding: '8px 12px', marginBottom: 14,
            fontSize: '0.75rem', color: 'var(--text2)',
          }}>
            <span style={{ fontSize: '0.85rem', flexShrink: 0 }}>💡</span>
            <span>{q.why}</span>
          </div>
        )}

        {/* Question text */}
        <div style={{
          fontSize: '1.05rem', fontWeight: 500, lineHeight: 1.6,
          marginBottom: 20, color: 'var(--text)',
        }}>
          {q.question}
        </div>

        {/* HR guidance */}
        {isHR && !isAnswered && (
          <div style={{
            background: 'rgba(148,163,184,0.06)',
            border: '1px solid rgba(148,163,184,0.15)',
            borderRadius: 8, padding: '10px 14px', marginBottom: 16,
            fontSize: '0.8rem', color: 'var(--text2)', lineHeight: 1.55,
          }}>
            <strong style={{ color: 'var(--text)' }}>Behavioral question —</strong> use the{' '}
            <strong style={{ color: 'var(--text)' }}>STAR method</strong>: describe the{' '}
            <em>Situation</em>, your <em>Task</em>, the <em>Action</em> you took, and the{' '}
            <em>Result</em> achieved. Aim for 100–200 words.
          </div>
        )}

        {/* ── Voice interface (unanswered) ── */}
        {!isAnswered && (
          <div>

            {/* Speaking phase */}
            {isSpeaking && (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                padding: '32px 0 24px', gap: 14,
              }}>
                <div style={{ display: 'flex', gap: 4, alignItems: 'center', height: 40 }}>
                  {[0.35, 0.6, 1, 0.75, 0.45, 0.85, 0.55, 0.9, 0.4, 0.65].map((h, i) => (
                    <div key={i} style={{
                      width: 4, borderRadius: 2,
                      background: 'var(--accent)',
                      height: `${h * 100}%`,
                      animation: `si-wave ${0.7 + i * 0.06}s ease-in-out infinite`,
                      animationDelay: `${i * 0.07}s`,
                    }} />
                  ))}
                </div>
                <span style={{ fontSize: '0.84rem', color: 'var(--text2)' }}>
                  Reading question aloud…
                </span>
                {showReplay && (
                  <button className="btn btn-ghost" onClick={handleReplay}
                    style={{ fontSize: '0.78rem', marginTop: 4 }}>
                    ↺ Replay Question
                  </button>
                )}
              </div>
            )}

            {/* Counting phase */}
            {isCounting && (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                padding: '28px 0 20px', gap: 12,
              }}>
                <div key={countdown} style={{
                  width: 72, height: 72, borderRadius: '50%',
                  border: '2px solid var(--accent)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '2rem', fontWeight: 700, color: 'var(--accent)',
                  animation: 'si-pop 0.25s ease-out forwards',
                }}>
                  {countdown}
                </div>
                <span style={{ fontSize: '0.84rem', color: 'var(--text2)' }}>
                  Recording starts in {countdown}s — prepare your answer
                </span>
                {showReplay && (
                  <button className="btn btn-ghost" onClick={handleReplay}
                    style={{ fontSize: '0.78rem' }}>
                    ↺ Replay Question
                  </button>
                )}
              </div>
            )}

            {/* Recording phase */}
            {isRecording && (
              <div style={{ marginTop: 4 }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10,
                }}>
                  <div style={{
                    width: 10, height: 10, borderRadius: '50%',
                    background: '#f87171',
                    animation: 'si-pulse 1.1s ease-in-out infinite',
                    flexShrink: 0,
                  }} />
                  <span style={{ fontSize: '0.82rem', color: '#f87171', fontWeight: 500 }}>
                    Recording
                  </span>
                  <span style={{ fontSize: '0.76rem', color: 'var(--muted)' }}>
                    — speak your answer clearly
                  </span>
                </div>

                <div style={{
                  minHeight: 110,
                  background: 'var(--surface2)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '12px 14px',
                  fontSize: '0.88rem', lineHeight: 1.65,
                  color: 'var(--text)',
                }}>
                  {(transcript || interimText) ? (
                    <>
                      <span>{transcript}</span>
                      <span style={{ color: 'var(--muted)' }}>{interimText}</span>
                    </>
                  ) : (
                    <span style={{ color: 'var(--muted)' }}>Listening… start speaking</span>
                  )}
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
                  <button
                    onClick={handleStopRecording}
                    style={{
                      padding: '7px 18px', borderRadius: 'var(--radius-sm)',
                      background: 'rgba(248,113,113,0.10)',
                      border: '1px solid rgba(248,113,113,0.3)',
                      color: '#f87171', cursor: 'pointer',
                      fontSize: '0.82rem', fontWeight: 500,
                    }}
                  >
                    ■ Stop Recording
                  </button>
                </div>
              </div>
            )}

            {/* Done phase — review & submit */}
            {isDone && (
              <div style={{ marginTop: 4 }}>
                <div style={{ fontSize: '0.74rem', color: 'var(--text2)', marginBottom: 6 }}>
                  Your answer
                </div>
                <div style={{
                  background: 'var(--surface2)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '12px 14px',
                  fontSize: '0.88rem', lineHeight: 1.65,
                  color: transcript.trim() ? 'var(--text)' : 'var(--muted)',
                  whiteSpace: 'pre-wrap',
                  minHeight: 60,
                }}>
                  {transcript.trim() || 'No speech detected — please try again.'}
                </div>
                {!(window.SpeechRecognition || window.webkitSpeechRecognition) && (
                  <p style={{ fontSize: '0.74rem', color: 'var(--muted)', marginTop: 6 }}>
                    Speech recognition not supported. Use Chrome for voice input.
                  </p>
                )}
              </div>
            )}

          </div>
        )}

        {/* Already answered — read-only */}
        {isAnswered && (
          <div style={{
            background: 'var(--surface2)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)', padding: '14px 16px',
            fontSize: '0.88rem', color: 'var(--text2)', lineHeight: 1.65,
            whiteSpace: 'pre-wrap',
          }}>
            {currentAnswer.userAnswer}
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{
            marginTop: 12,
            background: 'rgba(248,113,113,0.08)',
            border: '1px solid rgba(248,113,113,0.2)',
            borderRadius: 8, padding: '10px 14px',
            color: 'var(--red)', fontSize: '0.82rem',
          }}>
            ⚠ {error}
            <button onClick={onClearError} style={{
              marginLeft: 8, background: 'none', border: 'none',
              cursor: 'pointer', color: 'var(--red)', fontSize: '0.8rem',
            }}>✕</button>
          </div>
        )}

        {/* Score block */}
        {isAnswered && (
          <ScoreBlock answerData={{
            overall:       currentAnswer.overall,
            is_behavioral: currentAnswer.is_behavioral,
            angles:        currentAnswer.angles,
            modelAnswer:   currentAnswer.modelAnswer,
          }} />
        )}

        {/* Loading */}
        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 16 }}>
            <div className="spinner" style={{ width: 20, height: 20, borderWidth: 2 }} />
            <span style={{ fontSize: '0.82rem', color: 'var(--text2)' }}>Scoring your answer…</span>
          </div>
        )}

        {/* Navigation */}
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'center', marginTop: 24, paddingTop: 18,
          borderTop: '1px solid var(--border)',
        }}>
          <button className="btn btn-ghost" onClick={onPrev}
            disabled={currentIndex === 0} style={{ minWidth: 90 }}>
            ← Prev
          </button>

          <div style={{ display: 'flex', gap: 10 }}>
            {isDone && !isAnswered && (
              <button
                className="btn btn-primary"
                onClick={handleSubmit}
                disabled={!transcript.trim() || loading}
              >
                {loading ? 'Scoring…' : 'Submit Answer'}
              </button>
            )}

            {isAnswered && currentIndex < questions.length - 1 && (
              <button className="btn btn-primary" onClick={onNext}>
                Next →
              </button>
            )}

            {isAnswered && currentIndex === questions.length - 1 && (
              <button className="btn btn-green" onClick={onShowReport}>
                View Report →
              </button>
            )}

            {!isAnswered && allAnswered && (
              <button className="btn btn-green" onClick={onShowReport}>
                View Report →
              </button>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}
