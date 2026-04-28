import React, { useRef, useState } from 'react'
import axios from 'axios'

const API = 'http://localhost:8000'

export default function ConfidenceTestPage() {
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])

  const [recording, setRecording] = useState(false)
  const [audioBlob, setAudioBlob] = useState(null)
  const [audioUrl, setAudioUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const startRecording = async () => {
    setResult(null)
    setError(null)
    setAudioBlob(null)
    setAudioUrl(null)
    chunksRef.current = []

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream)
      mediaRecorderRef.current = mr

      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setAudioBlob(blob)
        setAudioUrl(URL.createObjectURL(blob))
        stream.getTracks().forEach(t => t.stop())
      }

      mr.start()
      setRecording(true)
    } catch (err) {
      setError('Microphone access denied: ' + err.message)
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop()
      setRecording(false)
    }
  }

  const analyze = async () => {
    if (!audioBlob) return
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const fd = new FormData()
      fd.append('audio', audioBlob, 'recording.webm')
      const res = await axios.post(`${API}/api/confidence`, fd)
      setResult(res.data)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message
      setError('Analysis failed: ' + msg)
    } finally {
      setLoading(false)
    }
  }

  const scoreColor = (score) => {
    if (score >= 7) return 'var(--green)'
    if (score >= 4) return 'var(--yellow)'
    return 'var(--red)'
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '40px 20px', background: 'var(--bg)',
    }}>
      <div style={{ width: '100%', maxWidth: 520 }}>

        {/* Header */}
        <div style={{ marginBottom: 32, textAlign: 'center' }}>
          <h1 style={{ fontSize: '1.8rem', marginBottom: 8 }}>
            Confidence <span style={{ color: 'var(--accent)' }}>Analyser</span>
          </h1>
          <p style={{ color: 'var(--text2)', fontSize: '0.88rem' }}>
            Record your voice — the model scores how confident you sound.
          </p>
        </div>

        {/* Recorder card */}
        <div className="card" style={{ marginBottom: 20 }}>

          {/* Waveform / status indicator */}
          <div style={{
            height: 72, borderRadius: 'var(--radius-sm)',
            background: 'var(--surface2)', border: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 20,
          }}>
            {recording ? (
              <div className="dot-pulse">
                <span /><span /><span />
              </div>
            ) : audioUrl ? (
              <audio controls src={audioUrl} style={{ width: '100%', padding: '0 12px' }} />
            ) : (
              <span style={{ color: 'var(--muted)', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
                no recording yet
              </span>
            )}
          </div>

          {/* Buttons */}
          <div style={{ display: 'flex', gap: 10 }}>
            {!recording ? (
              <button
                className="btn btn-primary"
                style={{ flex: 1 }}
                onClick={startRecording}
                disabled={loading}
              >
                <span style={{ fontSize: '1rem' }}>&#9679;</span> Record
              </button>
            ) : (
              <button
                className="btn btn-danger"
                style={{ flex: 1 }}
                onClick={stopRecording}
              >
                <span style={{ fontSize: '1rem' }}>&#9632;</span> Stop
              </button>
            )}

            <button
              className="btn btn-green"
              style={{ flex: 1 }}
              onClick={analyze}
              disabled={!audioBlob || loading || recording}
            >
              {loading ? 'Analysing…' : 'Analyse'}
            </button>
          </div>
        </div>

        {/* Loading */}
        {loading && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '16px 20px', borderRadius: 'var(--radius-sm)',
            background: 'var(--surface)', border: '1px solid var(--border)',
            color: 'var(--text2)', fontSize: '0.85rem',
          }}>
            <div className="spinner" style={{ width: 22, height: 22, borderWidth: 2 }} />
            Transcribing and extracting features…
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{
            padding: '14px 18px', borderRadius: 'var(--radius-sm)',
            background: 'var(--red-dim)', border: '1px solid rgba(248,113,113,0.25)',
            color: 'var(--red)', fontSize: '0.85rem',
          }}>
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="card fade-in" style={{ marginTop: 0 }}>
            <div style={{
              fontSize: '0.7rem', fontFamily: 'var(--font-mono)',
              color: 'var(--muted)', textTransform: 'uppercase',
              letterSpacing: '0.08em', marginBottom: 16,
            }}>
              Prediction Results
            </div>

            {/* Label */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              marginBottom: 20,
            }}>
              <span style={{ color: 'var(--text2)', fontSize: '0.88rem' }}>Label</span>
              <span style={{
                fontFamily: 'var(--font-mono)', fontWeight: 700,
                fontSize: '1rem',
                color: result.predicted_label === 'Confident' ? 'var(--green)' : 'var(--red)',
                background: result.predicted_label === 'Confident' ? 'var(--green-dim)' : 'var(--red-dim)',
                border: `1px solid ${result.predicted_label === 'Confident' ? 'rgba(52,211,153,0.3)' : 'rgba(248,113,113,0.3)'}`,
                padding: '4px 14px', borderRadius: 'var(--radius-pill)',
              }}>
                {result.predicted_label}
              </span>
            </div>

            {/* Score gauge */}
            <div style={{ marginBottom: 20 }}>
              <div style={{
                display: 'flex', justifyContent: 'space-between',
                marginBottom: 8, fontSize: '0.85rem',
              }}>
                <span style={{ color: 'var(--text2)' }}>Confidence Score</span>
                <span style={{
                  fontFamily: 'var(--font-mono)', fontWeight: 700,
                  fontSize: '1.1rem',
                  color: scoreColor(result.confidence_score_1_to_10),
                }}>
                  {result.confidence_score_1_to_10.toFixed(1)} / 10
                </span>
              </div>
              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{
                    width: `${(result.confidence_score_1_to_10 / 10) * 100}%`,
                    background: scoreColor(result.confidence_score_1_to_10),
                  }}
                />
              </div>
            </div>

            {/* Probability */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 14px',
              background: 'var(--surface2)', borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
            }}>
              <span style={{ color: 'var(--text2)' }}>P(Confident)</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text)' }}>
                {(result.confidence_probability * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
