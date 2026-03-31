/**
 * InterviewScreen.jsx
 * -------------------
 * Main interview UI: question card, textarea, score display, navigation.
 * Handles both technical (has model answer) and HR/behavioral (open-ended) questions.
 */

import React, { useState, useEffect } from 'react'
import ScoreBlock from './ScoreBlock'
import { CAT_META } from './ProfileStrip'

const MIN_CHARS = 20  // minimum before submit enabled

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
  const [text, setText] = useState('')

  // Reset textarea when question changes
  useEffect(() => {
    setText(currentAnswer?.userAnswer || '')
  }, [currentIndex, currentAnswer])

  if (!currentQuestion) return null

  const q            = currentQuestion
  const isAnswered   = !!currentAnswer
  const isHR         = !q.has_answer
  const catMeta      = CAT_META[q.category] || { color: '#6b7794', label: q.category }
  const canSubmit    = text.trim().length >= MIN_CHARS && !isAnswered && !loading

  const handleSubmit = () => {
    if (canSubmit) onSubmit(text.trim())
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && e.ctrlKey) handleSubmit()
  }

  return (
    <div style={{ maxWidth: 820, margin: '0 auto', padding: '28px 24px' }}>

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

        {/* Question dot nav */}
        <div style={{ display: 'flex', gap: 5, marginTop: 10, flexWrap: 'wrap' }}>
          {questions.map((_, i) => {
            const isActive   = i === currentIndex
            const isDone     = !!currentAnswer && i === currentIndex
            const answered   = i < questions.length  // placeholder
            const dotAnswered = !!questions[i]?._answered
            return (
              <div key={i} title={`Q${i + 1}`} style={{
                width: 8, height: 8, borderRadius: '50%',
                background: isActive
                  ? 'var(--accent)'
                  : 'var(--border2)',
                transition: 'background 0.2s',
              }} />
            )
          })}
        </div>
      </div>

      {/* Question card */}
      <div className="card fade-in" style={{ marginBottom: 0 }}>

        {/* Meta row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--muted)' }}>
            Q{String(currentIndex + 1).padStart(2, '0')}
          </span>

          {/* Category badge */}
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: '0.68rem',
            padding: '2px 10px', borderRadius: 'var(--radius-pill)',
            border: `1px solid ${catMeta.color}`,
            color: catMeta.color,
            background: `${catMeta.color}14`,
          }}>
            {catMeta.label}
          </span>

          {/* Difficulty */}
          <span className={`diff-badge diff-${q.difficulty}`}>{q.difficulty}</span>

          {/* Open-ended badge for HR */}
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
            borderRadius: 8, padding: '10px 14px', marginBottom: 14,
            fontSize: '0.8rem', color: 'var(--text2)', lineHeight: 1.55,
          }}>
            <strong style={{ color: 'var(--text)' }}>Behavioral question —</strong> use the{' '}
            <strong style={{ color: 'var(--text)' }}>STAR method</strong>:
            describe the <em>Situation</em>, your <em>Task</em>, the <em>Action</em> you took,
            and the <em>Result</em> achieved. Aim for 100–200 words.
          </div>
        )}

        {/* Answer textarea */}
        {!isAnswered ? (
          <>
            <textarea
              value={text}
              onChange={e => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isHR
                  ? 'Describe the situation, your actions, and the outcome…'
                  : 'Type your answer here… (Ctrl+Enter to submit)'
              }
              style={{ minHeight: 130 }}
              disabled={loading}
              autoFocus
            />
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              alignItems: 'center', marginTop: 6,
            }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--muted)' }}>
                {text.length} chars
                {text.length < MIN_CHARS && ` — ${MIN_CHARS - text.length} more to enable submit`}
              </span>
              <span style={{ fontSize: '0.68rem', color: 'var(--muted)' }}>Ctrl+Enter to submit</span>
            </div>
          </>
        ) : (
          /* Already answered — show user's text read-only */
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

        {/* Score block (appears after submission) */}
        {isAnswered && (
          <ScoreBlock answerData={{
            overall:      currentAnswer.overall,
            is_behavioral: currentAnswer.is_behavioral,
            angles:       currentAnswer.angles,
            modelAnswer:  currentAnswer.modelAnswer,
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
            {!isAnswered && (
              <button
                className="btn btn-primary"
                onClick={handleSubmit}
                disabled={!canSubmit}
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
