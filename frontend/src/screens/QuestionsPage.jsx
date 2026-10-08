import React, { useState } from 'react'

const DIFFICULTY_COLOR = {
  Easy:   { color: '#34d399', background: 'rgba(52,211,153,0.12)',  border: 'rgba(52,211,153,0.25)'  },
  Medium: { color: '#fbbf24', background: 'rgba(251,191,36,0.12)',  border: 'rgba(251,191,36,0.25)'  },
  Hard:   { color: '#FB7185', background: 'rgba(251,113,133,0.12)', border: 'rgba(251,113,133,0.25)' },
}

function Badge({ label, color, background, border }) {
  return (
    <span style={{
      fontFamily: 'var(--font-mono)', fontSize: '0.65rem', fontWeight: 600,
      color, background, border: `1px solid ${border}`,
      borderRadius: 'var(--radius-pill)', padding: '2px 9px',
      whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  )
}

function QuestionRow({ q, index }) {
  const [open, setOpen] = useState(false)
  const diff = DIFFICULTY_COLOR[q.difficulty] || DIFFICULTY_COLOR.Medium

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      padding: '16px 20px',
      display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: '0.7rem',
          color: 'var(--muted)', minWidth: 28, paddingTop: 2,
        }}>
          {String(index + 1).padStart(2, '0')}
        </span>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
            <Badge
              label={q.category}
              color="var(--accent2)"
              background="rgba(167,139,250,0.10)"
              border="rgba(167,139,250,0.22)"
            />
            <Badge label={q.difficulty} {...diff} />
            {!q.has_answer && (
              <Badge
                label="Behavioral"
                color="var(--muted)"
                background="transparent"
                border="var(--border2)"
              />
            )}
          </div>
          <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.55, color: 'var(--text)' }}>
            {q.question}
          </p>
        </div>
      </div>

      {q.has_answer && (
        <div style={{ paddingLeft: 42 }}>
          <button
            onClick={() => setOpen(o => !o)}
            style={{
              fontFamily: 'var(--font-mono)', fontSize: '0.65rem',
              color: 'var(--muted)', background: 'transparent',
              border: '1px solid var(--border2)', borderRadius: 'var(--radius-pill)',
              padding: '2px 10px', cursor: 'pointer',
            }}
          >
            {open ? 'Hide answer' : 'Show model answer'}
          </button>
          {open && (
            <p style={{
              margin: '10px 0 0',
              fontSize: '0.82rem', lineHeight: 1.6,
              color: 'var(--muted)',
              background: 'var(--surface2)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              padding: '10px 14px',
            }}>
              {q.model_answer}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default function QuestionsPage({ questions = [] }) {
  if (!questions.length) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        minHeight: '60vh', color: 'var(--muted)', fontFamily: 'var(--font-mono)',
        fontSize: '0.85rem',
      }}>
        No questions yet — upload a resume and complete the Ready screen first.
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 780, margin: '0 auto', padding: '32px 24px' }}>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
          Generated Questions
        </h2>
        <p style={{ margin: '4px 0 0', fontSize: '0.78rem', color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
          {questions.length} questions · click a row to reveal the model answer
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {questions.map((q, i) => (
          <QuestionRow key={q.id ?? i} q={q} index={i} />
        ))}
      </div>
    </div>
  )
}
