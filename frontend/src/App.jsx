/**
 * App.jsx
 * -------
 * Root component. Wires the useInterview hook to all screen components.
 * Flow: upload → ready → interview → report
 */

import React from 'react'
import { useInterview } from './hooks/useInterview'

import UploadScreen    from './components/UploadScreen'
import ProfileStrip    from './components/ProfileStrip'
import ReadyScreen     from './components/ReadyScreen'
import InterviewScreen from './components/InterviewScreen'
import ReportScreen    from './components/ReportScreen'

// ── Step indicator ────────────────────────────────────────

const STEPS = [
  { key: 'upload',    label: 'Upload Resume' },
  { key: 'ready',     label: 'Questions Ready' },
  { key: 'interview', label: 'Interview' },
  { key: 'report',    label: 'Report' },
]

function StepIndicator({ currentStep }) {
  const idx = STEPS.findIndex(s => s.key === currentStep)
  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      gap: 0, padding: '14px 36px',
      background: 'var(--surface)', borderBottom: '1px solid var(--border)',
    }}>
      {STEPS.map((step, i) => {
        const done   = i < idx
        const active = i === idx
        return (
          <React.Fragment key={step.key}>
            {i > 0 && (
              <div style={{
                width: 32, height: 1,
                background: done ? 'var(--accent)' : 'var(--border)',
                margin: '0 6px',
                transition: 'background 0.4s',
              }} />
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <div style={{
                width: 26, height: 26, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-mono)', fontSize: '0.72rem',
                fontWeight: 600,
                background: done
                  ? 'var(--green)'
                  : active
                    ? 'var(--accent)'
                    : 'var(--surface2)',
                color: (done || active) ? '#fff' : 'var(--muted)',
                border: done || active ? 'none' : '1px solid var(--border2)',
                transition: 'all 0.3s',
                flexShrink: 0,
              }}>
                {done ? '✓' : i + 1}
              </div>
              <span style={{
                fontSize: '0.75rem',
                color: active ? 'var(--text)' : 'var(--muted)',
                fontWeight: active ? 600 : 400,
                whiteSpace: 'nowrap',
              }}>
                {step.label}
              </span>
            </div>
          </React.Fragment>
        )
      })}
    </div>
  )
}

// ── Top bar ───────────────────────────────────────────────

function TopBar() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 36px', height: 56,
      background: 'var(--surface)',
      borderBottom: '1px solid var(--border)',
      position: 'sticky', top: 0, zIndex: 100,
    }}>
      <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', letterSpacing: '-0.02em' }}>
        Smart<span style={{ color: 'var(--accent)' }}>Interview</span>
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: '0.68rem',
        color: 'var(--accent2)',
        background: 'rgba(167,139,250,0.10)',
        border: '1px solid rgba(167,139,250,0.22)',
        borderRadius: 'var(--radius-pill)',
        padding: '3px 12px',
      }}>
        AI-Powered · 11 Categories · FAISS Vector Search
      </div>
    </div>
  )
}

// ── App ──────────────────────────────────────────────────

export default function App() {
  const interview = useInterview()

  const {
    step, loading, error,
    profile, questions,
    currentIndex, currentQuestion, currentAnswer,
    answeredCount, allAnswered, progress,
    report,
    handleUpload,
    startInterview,
    submitAnswer,
    goNext, goPrev,
    showReport, reset, retake,
    clearError,
  } = interview

  // Upload screen — full page, no bars
  if (step === 'upload') {
    return (
      <div style={{ minHeight: '100vh' }}>
        <TopBar />
        <UploadScreen
          onUpload={handleUpload}
          loading={loading}
          error={error}
        />
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <TopBar />
      <StepIndicator currentStep={step} />
      <ProfileStrip profile={profile} onReset={reset} />

      <div style={{ flex: 1 }}>
        {step === 'ready' && (
          <ReadyScreen
            profile={profile}
            questions={questions}
            onStart={startInterview}
          />
        )}

        {step === 'interview' && (
          <InterviewScreen
            questions={questions}
            currentIndex={currentIndex}
            currentQuestion={currentQuestion}
            currentAnswer={currentAnswer}
            answeredCount={answeredCount}
            allAnswered={allAnswered}
            progress={progress}
            loading={loading}
            error={error}
            onSubmit={submitAnswer}
            onNext={goNext}
            onPrev={goPrev}
            onShowReport={showReport}
            onClearError={clearError}
          />
        )}

        {step === 'report' && (
          <ReportScreen
            report={report}
            onRetake={retake}
            onReset={reset}
          />
        )}
      </div>
    </div>
  )
}
