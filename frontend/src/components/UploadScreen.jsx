/**
 * UploadScreen.jsx
 * ----------------
 * Drag-and-drop resume upload with validation + animated feedback.
 * Accepts PDF, DOCX, TXT.
 */

import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'

const ACCEPTED = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
}

const styles = {
  wrapper: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '32px 20px',
    background: 'radial-gradient(ellipse 80% 60% at 50% 0%, rgba(79,142,247,0.06) 0%, transparent 70%)',
  },
  inner: { maxWidth: 560, width: '100%' },
  logo: {
    fontFamily: 'var(--font-serif)',
    fontSize: '2.2rem',
    textAlign: 'center',
    marginBottom: 6,
    letterSpacing: '-0.02em',
  },
  logoAccent: { color: 'var(--accent)' },
  tagline: {
    textAlign: 'center',
    color: 'var(--text2)',
    fontSize: '0.9rem',
    marginBottom: 48,
  },
  dropzone: {
    border: '2px dashed var(--border2)',
    borderRadius: 'var(--radius)',
    padding: '56px 32px',
    textAlign: 'center',
    cursor: 'pointer',
    transition: 'all 0.25s',
    background: 'var(--surface)',
    outline: 'none',
  },
  dropzoneActive: {
    borderColor: 'var(--accent)',
    background: 'rgba(79,142,247,0.06)',
    transform: 'scale(1.01)',
  },
  icon: { fontSize: '3rem', marginBottom: 16, userSelect: 'none' },
  title: { fontFamily: 'var(--font-serif)', fontSize: '1.4rem', marginBottom: 8 },
  sub: { color: 'var(--text2)', fontSize: '0.85rem', lineHeight: 1.6 },
  formats: { display: 'flex', justifyContent: 'center', gap: 8, marginTop: 20 },
  formatChip: {
    fontFamily: 'var(--font-mono)',
    fontSize: '0.7rem',
    padding: '3px 10px',
    borderRadius: 'var(--radius-pill)',
    border: '1px solid var(--border2)',
    color: 'var(--text2)',
  },
  selectedFile: {
    marginTop: 24,
    background: 'var(--surface2)',
    border: '1px solid var(--border2)',
    borderRadius: 'var(--radius-sm)',
    padding: '14px 18px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  fileName: { fontSize: '0.88rem', fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  fileSize: { fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--text2)' },
  actions: { display: 'flex', gap: 10, marginTop: 20 },
  error: {
    marginTop: 16,
    background: 'rgba(248,113,113,0.08)',
    border: '1px solid rgba(248,113,113,0.25)',
    borderRadius: 'var(--radius-sm)',
    padding: '12px 16px',
    color: 'var(--red)',
    fontSize: '0.85rem',
  },
  features: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3,1fr)',
    gap: 12,
    marginTop: 36,
  },
  featureCard: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    padding: '16px',
    textAlign: 'center',
  },
  featureIcon: { fontSize: '1.4rem', marginBottom: 6 },
  featureLabel: { fontSize: '0.75rem', color: 'var(--text2)', lineHeight: 1.4 },
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

export default function UploadScreen({ onUpload, loading, error }) {
  const [file, setFile] = useState(null)
  const [localError, setLocalError] = useState('')

  const onDrop = useCallback((accepted, rejected) => {
    setLocalError('')
    if (rejected.length > 0) {
      setLocalError('Unsupported file type. Please upload a PDF, DOCX, or TXT file.')
      return
    }
    if (accepted.length > 0) {
      const f = accepted[0]
      if (f.size > 10 * 1024 * 1024) {
        setLocalError('File too large. Maximum size is 10 MB.')
        return
      }
      setFile(f)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxFiles: 1,
    disabled: loading,
  })

  const handleSubmit = () => {
    if (file) onUpload(file)
  }

  const displayError = localError || error

  return (
    <div style={styles.wrapper}>
      <div className="fade-in" style={styles.inner}>
        <div style={styles.logo}>
          Smart<span style={styles.logoAccent}>Interview</span>
        </div>
        <p style={styles.tagline}>
          Upload your resume. Get a personalized AI-powered interview — tailored to your exact skills and experience.
        </p>

        <div
          {...getRootProps()}
          style={{
            ...styles.dropzone,
            ...(isDragActive ? styles.dropzoneActive : {}),
          }}
        >
          <input {...getInputProps()} />
          <div style={styles.icon}>{isDragActive ? '📂' : '📄'}</div>
          <div style={styles.title}>
            {isDragActive ? 'Drop it here' : 'Drop your resume'}
          </div>
          <p style={styles.sub}>
            Drag & drop or <strong style={{ color: 'var(--accent)' }}>click to browse</strong>
            <br />PDF, DOCX, or TXT — any resume format
          </p>
          <div style={styles.formats}>
            {['.PDF', '.DOCX', '.TXT'].map(f => (
              <span key={f} style={styles.formatChip}>{f}</span>
            ))}
          </div>
        </div>

        {file && !loading && (
          <div style={styles.selectedFile}>
            <span style={{ fontSize: '1.2rem' }}>✅</span>
            <span style={styles.fileName}>{file.name}</span>
            <span style={styles.fileSize}>{formatBytes(file.size)}</span>
            <button
              className="btn btn-ghost"
              style={{ padding: '6px 12px', fontSize: '0.78rem' }}
              onClick={(e) => { e.stopPropagation(); setFile(null) }}
            >
              Remove
            </button>
          </div>
        )}

        {loading && (
          <div style={{ textAlign: 'center', marginTop: 24 }}>
            <div className="spinner" style={{ margin: '0 auto 12px' }} />
            <p style={{ color: 'var(--text2)', fontSize: '0.85rem' }}>
              Parsing resume & building embeddings…
            </p>
            <div className="dot-pulse" style={{ justifyContent: 'center', marginTop: 10 }}>
              <span /><span /><span />
            </div>
          </div>
        )}

        {displayError && !loading && (
          <div style={styles.error}>⚠ {displayError}</div>
        )}

        {file && !loading && (
          <div style={styles.actions}>
            <button
              className="btn btn-primary"
              style={{ flex: 1, justifyContent: 'center' }}
              onClick={handleSubmit}
              disabled={loading}
            >
              Analyze Resume →
            </button>
          </div>
        )}

        <div style={styles.features}>
          {[
            ['🔍', 'Smart Parsing', 'Extracts skills, roles & projects from any resume layout'],
            ['🧠', 'Vector Matching', 'FAISS cosine search tailors questions to your profile'],
            ['📊', 'Multi-angle Score', 'Conceptual, technical & completeness scoring per answer'],
          ].map(([icon, label, desc]) => (
            <div key={label} style={styles.featureCard}>
              <div style={styles.featureIcon}>{icon}</div>
              <div style={{ fontWeight: 600, fontSize: '0.8rem', marginBottom: 4 }}>{label}</div>
              <div style={styles.featureLabel}>{desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
