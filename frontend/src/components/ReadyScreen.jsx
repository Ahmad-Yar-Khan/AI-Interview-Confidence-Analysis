/**
 * ReadyScreen.jsx
 * ---------------
 * Configure screen shown after resume upload.
 * User optionally enters a target role and/or job description before
 * generating questions. Both fields are optional.
 */

import React, { useState } from 'react'

export default function ReadyScreen({ profile, onStart, loading, error }) {
  const [role, setRole] = useState('')
  const [jd,   setJd]   = useState('')

  if (!profile) return null

  const hasContext = role.trim() || jd.trim()

  return (
    <div style={{ maxWidth: 820, margin: '0 auto', padding: '28px 24px' }}>
      <div className="fade-in">

        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: '1.6rem', marginBottom: 6 }}>
            Ready, <span style={{ color: 'var(--accent)' }}>{profile.name.split(' ')[0]}</span>
          </h2>
          <p style={{ color: 'var(--text2)', fontSize: '0.88rem' }}>
            Resume uploaded successfully. Optionally tell us what role you're interviewing for
            — questions will be tailored to the gap between your profile and the target role.
          </p>
        </div>

        {/* Job context card */}
        <div className="card" style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 600, marginBottom: 4, fontSize: '0.88rem' }}>
            Target Role
            <span style={{
              marginLeft: 8, fontSize: '0.7rem', fontWeight: 400,
              color: 'var(--muted)', fontFamily: 'var(--font-mono)',
            }}>optional</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text2)', marginBottom: 10 }}>
            e.g. "Senior Backend Engineer at Google" or "ML Engineer (NLP focus)"
          </div>
          <input
            type="text"
            value={role}
            onChange={e => setRole(e.target.value)}
            placeholder="Job title or role…"
            maxLength={120}
            style={{
              width: '100%', boxSizing: 'border-box',
              background: 'var(--surface2)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              padding: '9px 12px',
              color: 'var(--text)', fontSize: '0.88rem',
              outline: 'none',
              transition: 'border-color 0.2s',
            }}
            onFocus={e => e.target.style.borderColor = 'var(--accent)'}
            onBlur={e  => e.target.style.borderColor = 'var(--border)'}
          />

          <div style={{ fontWeight: 600, marginBottom: 4, marginTop: 18, fontSize: '0.88rem' }}>
            Job Description
            <span style={{
              marginLeft: 8, fontSize: '0.7rem', fontWeight: 400,
              color: 'var(--muted)', fontFamily: 'var(--font-mono)',
            }}>optional</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text2)', marginBottom: 10 }}>
            Paste the JD and Gemini will generate questions that probe your fit for the specific requirements.
          </div>
          <textarea
            value={jd}
            onChange={e => setJd(e.target.value)}
            placeholder="Paste job description here…"
            rows={6}
            maxLength={4000}
            style={{
              width: '100%', boxSizing: 'border-box',
              background: 'var(--surface2)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              padding: '9px 12px',
              color: 'var(--text)', fontSize: '0.85rem',
              lineHeight: 1.55, resize: 'vertical',
              fontFamily: 'inherit', outline: 'none',
              transition: 'border-color 0.2s',
            }}
            onFocus={e => e.target.style.borderColor = 'var(--accent)'}
            onBlur={e  => e.target.style.borderColor = 'var(--border)'}
          />
          {jd.length > 3500 && (
            <div style={{ fontSize: '0.72rem', color: 'var(--muted)', marginTop: 4, textAlign: 'right' }}>
              {jd.length}/4000
            </div>
          )}

          {hasContext && (
            <div style={{
              marginTop: 14,
              background: 'rgba(99,102,241,0.07)',
              border: '1px solid rgba(99,102,241,0.2)',
              borderRadius: 8, padding: '10px 14px',
              fontSize: '0.78rem', color: 'var(--text2)', lineHeight: 1.55,
            }}>
              <span style={{ color: 'var(--accent)', fontWeight: 600 }}>RAG mode active —</span>{' '}
              questions will be generated using your resume <em>and</em> the target role context,
              focusing on skills the role requires that your profile may not fully cover.
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
                desc: 'Semantic similarity between your answer and the model answer',
                sub: 'Technical questions',
              },
              {
                icon: '⚙️', label: 'Technical',
                desc: 'Domain-specific keyword overlap relevant to the question category',
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

        {/* Error */}
        {error && (
          <div style={{
            marginBottom: 16,
            background: 'rgba(248,113,113,0.08)',
            border: '1px solid rgba(248,113,113,0.2)',
            borderRadius: 8, padding: '10px 14px',
            color: 'var(--red)', fontSize: '0.82rem',
          }}>
            ⚠ {error}
          </div>
        )}

        {/* Start button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button
            className="btn btn-primary"
            style={{ fontSize: '1rem', padding: '13px 32px', minWidth: 180 }}
            onClick={() => onStart(role, jd)}
            disabled={loading}
          >
            {loading
              ? <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                  Generating questions…
                </span>
              : hasContext
                ? '▶ Generate & Start'
                : '▶ Start Interview'
            }
          </button>
          {!loading && (
            <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
              ~24–48 seconds to generate
            </span>
          )}
        </div>

      </div>
    </div>
  )
}
