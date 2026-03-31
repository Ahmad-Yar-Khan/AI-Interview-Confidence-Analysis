/**
 * ScoreBlock.jsx
 * --------------
 * Renders the score result after an answer is submitted.
 * Two modes:
 *   - Technical  : ring score + conceptual/technical/completeness angles + model answer
 *   - Behavioral : ring score + effort/richness/structure angles + STAR method tip
 */

import React from 'react'

function getScoreColor(score) {
  if (score >= 75) return 'var(--green)'
  if (score >= 50) return 'var(--yellow)'
  return 'var(--red)'
}

function getGrade(score) {
  if (score >= 85) return 'Excellent'
  if (score >= 70) return 'Good'
  if (score >= 50) return 'Fair'
  return 'Needs Improvement'
}

function ScoreRing({ score }) {
  const r     = 44
  const circ  = 2 * Math.PI * r
  const fill  = (score / 100) * circ
  const color = getScoreColor(score)

  return (
    <div style={{ position: 'relative', width: 110, height: 110, flexShrink: 0 }}>
      <svg width="110" height="110" viewBox="0 0 110 110" style={{ transform: 'rotate(-90deg)' }}>
        <circle cx="55" cy="55" r={r} fill="none" stroke="var(--border2)" strokeWidth="9" />
        <circle cx="55" cy="55" r={r} fill="none" stroke={color} strokeWidth="9"
          strokeDasharray={`${fill} ${circ}`} strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 0.8s cubic-bezier(0.4,0,0.2,1)' }} />
      </svg>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontFamily: 'var(--font-serif)', fontSize: '1.7rem', color, lineHeight: 1 }}>
          {score}
        </span>
        <span style={{ fontSize: '0.65rem', color: 'var(--muted)' }}>/100</span>
      </div>
    </div>
  )
}

function AngleCard({ label, value, description }) {
  const color = getScoreColor(value)
  return (
    <div style={{
      background: 'var(--surface3)', borderRadius: 8,
      padding: '10px 12px', textAlign: 'center',
    }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.05rem', color, fontWeight: 500 }}>
        {value}
      </div>
      <div style={{ fontSize: '0.68rem', color: 'var(--text2)', marginTop: 2, fontWeight: 600 }}>
        {label}
      </div>
      {description && (
        <div style={{ fontSize: '0.62rem', color: 'var(--muted)', marginTop: 3, lineHeight: 1.4 }}>
          {description}
        </div>
      )}
    </div>
  )
}

export default function ScoreBlock({ answerData }) {
  if (!answerData) return null

  const { overall, is_behavioral, angles, modelAnswer } = answerData
  const color = getScoreColor(overall)

  const technicalAngles = [
    { key: 'conceptual',   label: 'Conceptual',   desc: 'Semantic similarity' },
    { key: 'technical',    label: 'Technical',    desc: 'Domain term overlap' },
    { key: 'completeness', label: 'Completeness', desc: 'Key point coverage' },
  ]

  const behavioralAngles = [
    { key: 'conceptual',   label: 'Effort',    desc: 'Answer length & depth' },
    { key: 'technical',    label: 'Richness',  desc: 'Behavioral keyword density' },
    { key: 'completeness', label: 'Structure', desc: 'STAR method signals' },
  ]

  const angleList = is_behavioral ? behavioralAngles : technicalAngles

  return (
    <div className="fade-in" style={{
      background: 'var(--surface2)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      padding: 20,
      marginTop: 18,
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
        <ScoreRing score={overall} />

        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{
              fontWeight: 700, fontSize: '0.95rem', color,
            }}>
              {getGrade(overall)}
            </span>
            {is_behavioral && (
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: '0.65rem',
                padding: '2px 8px', borderRadius: 'var(--radius-pill)',
                background: 'rgba(148,163,184,0.12)',
                border: '1px solid rgba(148,163,184,0.25)',
                color: 'var(--text2)',
              }}>
                Effort Score
              </span>
            )}
          </div>

          {/* Angle cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
            {angleList.map(({ key, label, desc }) => (
              <AngleCard
                key={key}
                label={label}
                value={angles?.[key] ?? 0}
                description={desc}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Model answer (technical only) */}
      {!is_behavioral && modelAnswer && (
        <div style={{
          marginTop: 16,
          background: 'var(--surface)',
          borderLeft: '3px solid var(--accent)',
          borderRadius: '0 8px 8px 0',
          padding: '12px 16px',
        }}>
          <div style={{
            fontSize: '0.68rem', textTransform: 'uppercase',
            letterSpacing: '0.08em', color: 'var(--text2)',
            fontWeight: 600, marginBottom: 6,
          }}>
            Model Answer
          </div>
          <div style={{ fontSize: '0.84rem', color: 'var(--text2)', lineHeight: 1.65 }}>
            {modelAnswer}
          </div>
        </div>
      )}

      {/* STAR tip for behavioral */}
      {is_behavioral && (
        <div style={{
          marginTop: 16,
          background: 'rgba(148,163,184,0.06)',
          border: '1px solid rgba(148,163,184,0.15)',
          borderRadius: 8,
          padding: '12px 16px',
        }}>
          <div style={{
            fontSize: '0.68rem', textTransform: 'uppercase',
            letterSpacing: '0.08em', color: 'var(--text2)',
            fontWeight: 600, marginBottom: 6,
          }}>
            💡 STAR Method Tip
          </div>
          <div style={{ fontSize: '0.82rem', color: 'var(--muted)', lineHeight: 1.65 }}>
            Strong behavioral answers follow: <strong style={{ color: 'var(--text2)' }}>Situation → Task → Action → Result</strong>.
            Include specific context, what you did, and a measurable outcome.
          </div>
        </div>
      )}
    </div>
  )
}
