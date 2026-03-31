/**
 * ReportScreen.jsx
 * ----------------
 * Full interview performance report.
 * Shows: overall score, category breakdown, per-question detail,
 * angle averages — distinguishes technical vs behavioral scoring.
 */

import React, { useState } from 'react'
import { CAT_META } from './ProfileStrip'

function getScoreColor(score) {
  if (score >= 75) return 'var(--green)'
  if (score >= 50) return 'var(--yellow)'
  return 'var(--red)'
}

function getGrade(score) {
  if (score >= 85) return { label: 'Excellent', emoji: '🏆' }
  if (score >= 70) return { label: 'Good',      emoji: '✅' }
  if (score >= 50) return { label: 'Fair',       emoji: '📈' }
  return               { label: 'Needs Work',  emoji: '💪' }
}

function StatCard({ value, label, color }) {
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius)', padding: '20px 16px', textAlign: 'center',
    }}>
      <div style={{ fontFamily: 'var(--font-serif)', fontSize: '2rem', color: color || 'var(--text)', lineHeight: 1 }}>
        {value}
      </div>
      <div style={{ fontSize: '0.73rem', color: 'var(--text2)', marginTop: 6 }}>{label}</div>
    </div>
  )
}

function CategoryRow({ name, data }) {
  const meta  = CAT_META[name] || { color: '#6b7794', label: name }
  const color = getScoreColor(data.average)
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '160px 1fr 56px',
      gap: 12, alignItems: 'center',
      padding: '12px 20px',
      borderBottom: '1px solid var(--border)',
    }}>
      <div style={{ fontSize: '0.78rem', color: meta.color, fontWeight: 500 }}>
        {meta.label}
        {data.is_behavioral && (
          <span style={{ fontSize: '0.62rem', color: 'var(--muted)', display: 'block' }}>Effort Score</span>
        )}
      </div>
      <div>
        <div style={{ height: 7, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
          <div style={{
            height: '100%', width: `${data.average}%`,
            background: `linear-gradient(90deg, ${meta.color}, ${meta.color}99)`,
            borderRadius: 4,
            transition: 'width 1s cubic-bezier(0.4,0,0.2,1)',
          }} />
        </div>
        <div style={{ fontSize: '0.68rem', color: 'var(--muted)', marginTop: 3 }}>
          {data.count} question{data.count !== 1 ? 's' : ''}
        </div>
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: '0.82rem',
        color, textAlign: 'right', fontWeight: 600,
      }}>
        {data.average}
      </div>
    </div>
  )
}

export default function ReportScreen({ report, onRetake, onReset }) {
  const [expandedIdx, setExpandedIdx] = useState(null)

  if (!report) return null

  const {
    candidate_name, candidate_title,
    total_questions, answered,
    average_score, best_score, worst_score,
    category_breakdown, answers,
  } = report

  const grade  = getGrade(average_score)
  const color  = getScoreColor(average_score)

  // Average angles across technical answers only
  const techAnswers = answers.filter(a => !a.score.is_behavioral)
  const avgAngle = (key) => techAnswers.length
    ? Math.round(techAnswers.reduce((s, a) => s + (a.score.angles?.[key] || 0), 0) / techAnswers.length)
    : null

  const behavAnswers = answers.filter(a => a.score.is_behavioral)

  return (
    <div style={{ maxWidth: 820, margin: '0 auto', padding: '28px 24px' }}>

      {/* Header */}
      <div className="fade-in" style={{
        background: 'linear-gradient(135deg, var(--surface) 0%, #0e1525 100%)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)', padding: '36px 32px',
        textAlign: 'center', marginBottom: 24,
      }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
          Interview Complete
        </div>
        <h1 style={{ fontSize: '2rem', marginBottom: 4 }}>Performance Report</h1>
        {candidate_title && (
          <div style={{ fontSize: '0.83rem', color: 'var(--text2)', marginBottom: 20 }}>
            {candidate_name} · {candidate_title}
          </div>
        )}

        {/* Big score */}
        <div style={{ fontFamily: 'var(--font-serif)', fontSize: '5rem', color, lineHeight: 1, margin: '12px 0' }}>
          {average_score}
        </div>
        <div style={{ fontSize: '0.85rem', color: 'var(--text2)', marginBottom: 20 }}>
          {grade.emoji} {grade.label} — {answered}/{total_questions} questions answered
        </div>

        {/* Angle averages (technical only) */}
        {techAnswers.length > 0 && (
          <div style={{ display: 'flex', justifyContent: 'center', gap: 0 }}>
            {[
              { label: 'Conceptual',   val: avgAngle('conceptual') },
              { label: 'Technical',    val: avgAngle('technical') },
              { label: 'Completeness', val: avgAngle('completeness') },
            ].map(({ label, val }, i) => (
              <React.Fragment key={label}>
                {i > 0 && <div style={{ width: 1, background: 'var(--border)', margin: '0 20px' }} />}
                <div style={{ textAlign: 'center', padding: '0 16px' }}>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.4rem', color: getScoreColor(val) }}>
                    {val ?? '—'}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>{label}</div>
                </div>
              </React.Fragment>
            ))}
          </div>
        )}
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <StatCard value={best_score}    label="Best Score"    color="var(--green)" />
        <StatCard value={average_score} label="Average Score" color={color} />
        <StatCard value={worst_score}   label="Lowest Score"  color="var(--red)" />
      </div>

      {/* Category breakdown */}
      {Object.keys(category_breakdown).length > 1 && (
        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', marginBottom: 24, overflow: 'hidden',
        }}>
          <div style={{
            padding: '14px 20px', borderBottom: '1px solid var(--border)',
            fontSize: '0.85rem', fontWeight: 600,
          }}>
            Category Breakdown
          </div>
          {Object.entries(category_breakdown)
            .sort((a, b) => b[1].average - a[1].average)
            .map(([cat, data]) => (
              <CategoryRow key={cat} name={cat} data={data} />
            ))
          }
        </div>
      )}

      {/* Per-question breakdown */}
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius)', marginBottom: 24, overflow: 'hidden',
      }}>
        <div style={{
          padding: '14px 20px', borderBottom: '1px solid var(--border)',
          fontSize: '0.85rem', fontWeight: 600,
        }}>
          Question-by-Question Breakdown
        </div>

        {answers.map((a, i) => {
          const catMeta   = CAT_META[a.category] || { color: '#6b7794' }
          const sc        = a.score.overall
          const scColor   = getScoreColor(sc)
          const isOpen    = expandedIdx === i
          const isBehav   = a.score.is_behavioral

          return (
            <div key={i} style={{ borderBottom: '1px solid var(--border)' }}>
              {/* Summary row (clickable) */}
              <div
                onClick={() => setExpandedIdx(isOpen ? null : i)}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '28px 1fr 90px 48px 24px',
                  gap: 10, alignItems: 'center',
                  padding: '13px 20px', cursor: 'pointer',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--surface2)'}
                onMouseLeave={e => e.currentTarget.style.background = ''}
              >
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: 'var(--muted)' }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <div>
                  <div style={{ fontSize: '0.83rem', lineHeight: 1.4 }}>{a.question}</div>
                  <div style={{ fontSize: '0.67rem', color: catMeta.color, marginTop: 2 }}>
                    {a.category} · <span className={`diff-badge diff-${a.difficulty}`} style={{ fontSize: '0.62rem', padding: '1px 6px' }}>{a.difficulty}</span>
                    {isBehav && <span style={{ color: 'var(--muted)', marginLeft: 4 }}>· Effort Score</span>}
                  </div>
                </div>
                {/* Mini score bar */}
                <div>
                  <div style={{ height: 5, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${sc}%`, background: scColor, borderRadius: 3 }} />
                  </div>
                </div>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: '0.78rem',
                  color: scColor, fontWeight: 600, textAlign: 'right',
                }}>
                  {sc}%
                </div>
                <span style={{ color: 'var(--muted)', fontSize: '0.8rem', textAlign: 'center' }}>
                  {isOpen ? '▲' : '▼'}
                </span>
              </div>

              {/* Expanded detail */}
              {isOpen && (
                <div style={{
                  padding: '0 20px 16px',
                  background: 'var(--surface2)',
                  borderTop: '1px solid var(--border)',
                }}>
                  <div style={{ paddingTop: 14 }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                      Your Answer
                    </div>
                    <div style={{ fontSize: '0.83rem', color: 'var(--text2)', lineHeight: 1.6, marginBottom: 14 }}>
                      {a.user_answer}
                    </div>

                    {!isBehav && a.model_answer && (
                      <>
                        <div style={{ fontSize: '0.72rem', color: 'var(--muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                          Model Answer
                        </div>
                        <div style={{
                          fontSize: '0.83rem', color: 'var(--text2)', lineHeight: 1.6,
                          borderLeft: '3px solid var(--accent)',
                          paddingLeft: 12,
                        }}>
                          {a.model_answer}
                        </div>
                      </>
                    )}

                    {/* Angle breakdown */}
                    <div style={{ display: 'flex', gap: 10, marginTop: 14, flexWrap: 'wrap' }}>
                      {Object.entries(a.score.angles || {}).map(([key, val]) => {
                        const labels = isBehav
                          ? { conceptual: 'Effort', technical: 'Richness', completeness: 'Structure' }
                          : { conceptual: 'Conceptual', technical: 'Technical', completeness: 'Completeness' }
                        return (
                          <div key={key} style={{
                            background: 'var(--surface3)', borderRadius: 8,
                            padding: '8px 14px', textAlign: 'center', minWidth: 80,
                          }}>
                            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', color: getScoreColor(val) }}>{val}</div>
                            <div style={{ fontSize: '0.65rem', color: 'var(--muted)', marginTop: 2 }}>{labels[key] || key}</div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', paddingBottom: 40 }}>
        <button className="btn btn-ghost" onClick={onReset}>↺ New Resume</button>
        <button className="btn btn-primary" onClick={onRetake}>Retake Interview</button>
      </div>
    </div>
  )
}
