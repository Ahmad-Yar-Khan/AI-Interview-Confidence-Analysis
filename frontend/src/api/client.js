/**
 * api.js
 * ------
 * All HTTP calls to the FastAPI backend.
 * Base URL is proxied via Vite dev server → http://localhost:8000
 */

import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// ── Error helper ─────────────────────────────────────────
function extractError(err) {
  return err?.response?.data?.detail
    || err?.response?.data?.message
    || err?.message
    || 'An unexpected error occurred.'
}

// ── 1. Upload resume ─────────────────────────────────────
/**
 * @param {File} file  PDF, DOCX, or TXT
 * @returns {{ session_id: string, profile: object }}
 */
export async function uploadResume(file) {
  const form = new FormData()
  form.append('file', file)
  try {
    const { data } = await api.post('/upload-resume', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

// ── 2. Job-title dropdown options ─────────────────────────
/**
 * @returns {{ categories: {category: string, roles: {slug: string, name: string}[]}[],
 *             other: {slug: string, name: string} }}
 */
export async function fetchRoles() {
  try {
    const { data } = await api.get('/roles')
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

// ── 3. Fetch tailored questions ───────────────────────────
/**
 * @param {string} sessionId
 * @param {number} total     Opening questions to generate (default 5; follow-ups come later)
 * @param {string} role      Role slug from fetchRoles(), or 'other'
 * @param {number} years     Years of experience
 * @returns {{ questions: object[], role_context: object }}
 */
export async function fetchQuestions(sessionId, total = 5, role = 'other', years = null) {
  try {
    const params = { total, role }
    if (years !== null && years !== undefined) params.years = years
    const { data } = await api.get(`/questions/${sessionId}`, { params })
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

// ── 4. Score a single answer ─────────────────────────────
/**
 * @param {{
 *   session_id: string,
 *   question_id: string,
 *   question_text: string,
 *   model_answer: string,
 *   user_answer: string,
 *   category: string,
 *   difficulty: string,
 * }} payload
 * @returns {{ question_id, overall, angles, model_answer }}
 */
export async function scoreAnswer(payload) {
  try {
    const { data } = await api.post('/score', payload)
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

// ── 4b. Follow-up for a weak, already-scored answer ───────
/**
 * @param {string} sessionId
 * @param {string} questionId  the question whose answer scored weakly
 * @returns {{ followup: object | null }}
 */
export async function requestFollowup(sessionId, questionId) {
  try {
    const { data } = await api.post('/followup', { session_id: sessionId, question_id: questionId })
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

// ── 5. Get full report ────────────────────────────────────
/**
 * @param {string} sessionId
 */
export async function fetchReport(sessionId) {
  try {
    const { data } = await api.get(`/report/${sessionId}`)
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

// ── 6. Delete session ─────────────────────────────────────
export async function deleteSession(sessionId) {
  try {
    await api.delete(`/session/${sessionId}`)
  } catch (_) {
    // best-effort
  }
}

// ── 7. Confidence analysis from audio ─────────────────────
/**
 * @param {Blob} audioBlob  Audio recorded by MediaRecorder
 * @returns {{ predicted_label, confidence_probability, confidence_score_1_to_10 }}
 */
export async function submitConfidence(audioBlob) {
  try {
    const ext  = (audioBlob.type || '').includes('mp4') ? 'mp4' : 'webm'
    const form = new FormData()
    form.append('audio', audioBlob, `recording.${ext}`)
    const { data } = await api.post('/confidence', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}
