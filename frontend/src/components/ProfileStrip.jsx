/**
 * ProfileStrip.jsx
 * ----------------
 * Sticky bar showing parsed resume: name, title, skills, all 11 category weights.
 */

import React from 'react'

// Styles for all 11 canonical categories
export const CAT_META = {
  'AI & Data Science':    { color: '#4f8ef7', label: 'AI / DS' },
  'Software Engineering': { color: '#34d399', label: 'Software Eng' },
  'SQL & Databases':      { color: '#fbbf24', label: 'SQL & DB' },
  'Cloud & Containers':   { color: '#f472b6', label: 'Cloud' },
  'DevOps':               { color: '#fb923c', label: 'DevOps' },
  'DSA & Algorithms':     { color: '#a78bfa', label: 'DSA' },
  'Operating Systems':    { color: '#38bdf8', label: 'OS' },
  'Computer Networks':    { color: '#4ade80', label: 'Networks' },
  'Distributed Systems':  { color: '#f43f5e', label: 'Distributed' },
  'Concurrency':          { color: '#e879f9', label: 'Concurrency' },
  'HR & Behavioral':      { color: '#94a3b8', label: 'HR / Behavioral' },
}

function getInitials(name = '') {
  return name.split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase() || '').join('')
}

export default function ProfileStrip({ profile, onReset }) {
  if (!profile) return null
  const { name, title, skills = [], category_weights = {} } = profile

  return (
    <div style={{
      background: 'var(--surface)',
      borderBottom: '1px solid var(--border)',
      padding: '14px 36px',
      display: 'flex',
      alignItems: 'center',
      gap: 18,
      flexWrap: 'wrap',
      position: 'sticky',
      top: 56,
      zIndex: 90,
    }}>
      {/* Avatar */}
      <div style={{
        width: 44, height: 44, borderRadius: '50%',
        background: 'linear-gradient(135deg, var(--accent), var(--accent2))',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-serif)', fontSize: '1rem', color: '#fff', flexShrink: 0,
      }}>
        {getInitials(name)}
      </div>

      {/* Name + title */}
      <div style={{ flexShrink: 0 }}>
        <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1rem', lineHeight: 1.2 }}>{name}</div>
        {title && <div style={{ fontSize: '0.72rem', color: 'var(--text2)', marginTop: 2 }}>{title}</div>}
      </div>

      {/* Skills */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, flex: 1, minWidth: 120 }}>
        {skills.slice(0, 10).map(skill => (
          <span key={skill} className="chip"
            style={{ color: 'var(--accent2)', borderColor: 'rgba(167,139,250,0.3)', fontSize: '0.67rem' }}>
            {skill}
          </span>
        ))}
        {skills.length > 10 && (
          <span className="chip" style={{ color: 'var(--muted)', fontSize: '0.67rem' }}>
            +{skills.length - 10}
          </span>
        )}
      </div>

      {/* Category weight pills — only show relevant ones (>= 15%) */}
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', flexShrink: 0 }}>
        {Object.entries(CAT_META).map(([cat, meta]) => {
          const weight = category_weights[cat] || 0
          const pct    = Math.round(weight * 100)
          if (pct < 10) return null
          const isActive = pct >= 30
          return (
            <div key={cat} title={`${cat}: ${pct}% match`} style={{
              fontFamily: 'var(--font-mono)', fontSize: '0.65rem',
              padding: '2px 9px', borderRadius: 'var(--radius-pill)',
              border: `1px solid ${meta.color}`,
              color: meta.color,
              background: `${meta.color}14`,
              opacity: isActive ? 1 : 0.35,
              cursor: 'default',
            }}>
              {meta.label} {pct}%
            </div>
          )
        })}
      </div>

      {/* Reset */}
      <button className="btn btn-ghost"
        style={{ padding: '5px 12px', fontSize: '0.72rem', flexShrink: 0 }}
        onClick={onReset} title="Upload a different resume">
        ↺ New Resume
      </button>
    </div>
  )
}
