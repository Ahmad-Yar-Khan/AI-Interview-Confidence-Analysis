/**
 * ReadyScreen.jsx
 * ---------------
 * Shown after resume is parsed and questions are selected.
 * Displays: profile summary, category distribution, question preview, scoring explainer.
 */

import React from 'react'
import { CAT_META } from './ProfileStrip'

export default function ReadyScreen({ profile, questions, onStart }) {
  if (!profile || !questions.length) return null

  // Count per category
  const catCounts = {}
  questions.forEach(q => {
    catCounts[q.category] = (catCounts[q.category] || 0) + 1
  })

  const diffCounts = { Easy: 0, Medium: 0, Hard: 0 }
  questions.forEach(q => { diffCounts[q.difficulty] = (diffCounts[q.difficulty] || 0) + 1 })

  return (
    <div style={{ maxWidth: 820, margin: '0 auto', padding: '28px 24px' }}>
      <div className="fade-in">

        {/* Ready header */}
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: '1.6rem', marginBottom: 6 }}>
            Interview Ready, <span style={{ color: 'var(--accent)' }}>{profile.name.split(' ')[0]}</span>
          </h2>
          <p style={{ color: 'var(--text2)', fontSize: '0.88rem' }}>
            Vector search matched <strong style={{ color: 'var(--text)' }}>{questions.length} questions</strong> tailored
            to your skills and experience — weighted by resume relevance.
          </p>
        </div>

        {/* Category distribution */}
        <div className="card" style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 600, marginBottom: 14, fontSize: '0.88rem' }}>
            Question Distribution
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px,1fr))', gap: 10 }}>
            {Object.entries(catCounts).map(([cat, count]) => {
              const meta = CAT_META[cat] || { color: '#6b7794', label: cat }
              return (
                <div key={cat} style={{
                  background: 'var(--surface2)',
                  border: `1px solid var(--border)`,
                  borderLeft: `3px solid ${meta.color}`,
                  borderRadius: 'var(--radius-sm)',
                  padding: '12px 14px',
                }}>
                  <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.6rem', color: meta.color, lineHeight: 1 }}>
                    {count}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text2)', marginTop: 4, lineHeight: 1.3 }}>
                    {meta.label}
                    {cat === 'HR & Behavioral' && (
                      <span style={{ color: 'var(--muted)', display: 'block' }}>Open-ended</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Difficulty split */}
          <div style={{ display: 'flex', gap: 12, marginTop: 14 }}>
            {Object.entries(diffCounts).map(([d, n]) => n > 0 && (
              <span key={d} className={`diff-badge diff-${d}`}>{n} {d}</span>
            ))}
          </div>
        </div>

        {/* Question preview */}
        <div className="card" style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 600, marginBottom: 12, fontSize: '0.88rem' }}>
            Preview (first {Math.min(4, questions.length)} questions)
          </div>
          {questions.slice(0, 4).map((q, i) => {
            const meta = CAT_META[q.category] || { color: '#6b7794' }
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'flex-start', gap: 12,
                padding: '10px 0',
                borderBottom: i < 3 ? '1px solid var(--border)' : 'none',
              }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: 'var(--accent)', marginTop: 2, flexShrink: 0 }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <div style={{ flex: 1, fontSize: '0.83rem', lineHeight: 1.45 }}>
                  {q.question}
                  {!q.has_answer && (
                    <span style={{ fontSize: '0.68rem', color: 'var(--muted)', marginLeft: 6 }}>
                      (open-ended)
                    </span>
                  )}
                </div>
                <span className={`diff-badge diff-${q.difficulty}`} style={{ flexShrink: 0 }}>
                  {q.difficulty}
                </span>
              </div>
            )
          })}
          {questions.length > 4 && (
            <div style={{ fontSize: '0.75rem', color: 'var(--muted)', paddingTop: 10 }}>
              +{questions.length - 4} more questions…
            </div>
          )}
        </div>

        {/* Scoring explainer */}
        <div className="card" style={{ marginBottom: 24 }}>
          <div style={{ fontWeight: 600, marginBottom: 12, fontSize: '0.88rem' }}>
            How Scoring Works
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px,1fr))', gap: 12 }}>
            {[
              {
                icon: '🧠', label: 'Conceptual',
                desc: 'TF-IDF cosine similarity between your answer and the model answer',
                sub: 'Technical questions',
              },
              {
                icon: '⚙️', label: 'Technical',
                desc: 'Overlap of domain-specific keywords relevant to the question category',
                sub: 'Technical questions',
              },
              {
                icon: '📋', label: 'Completeness',
                desc: 'Coverage of key points from the model answer in your response',
                sub: 'Technical questions',
              },
              {
                icon: '🎯', label: 'Effort Score',
                desc: 'Effort, behavioral keyword richness, and STAR method structure',
                sub: 'HR & Behavioral',
              },
            ].map(({ icon, label, desc, sub }) => (
              <div key={label} style={{
                background: 'var(--surface2)', borderRadius: 'var(--radius-sm)', padding: '14px',
              }}>
                <div style={{ fontSize: '1.1rem', marginBottom: 6 }}>{icon}</div>
                <div style={{ fontWeight: 600, fontSize: '0.82rem', marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: '0.73rem', color: 'var(--text2)', lineHeight: 1.5, marginBottom: 4 }}>{desc}</div>
                <div style={{ fontSize: '0.65rem', color: 'var(--muted)', fontStyle: 'italic' }}>{sub}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Start button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button className="btn btn-primary" style={{ fontSize: '1rem', padding: '13px 32px' }}
            onClick={onStart}>
            ▶ Start Interview
          </button>
          <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
            ~{questions.length * 2}–{questions.length * 4} minutes
          </span>
        </div>

      </div>
    </div>
  )
}
