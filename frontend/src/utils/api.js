/**
 * api.js
 * ------
 * All HTTP calls to the FastAPI backend.
 * Base URL is proxied via Vite dev server → http://localhost:8000
 */

import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
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
    const { data } = await api.post('/parse-resume', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

// ── 2. Fetch tailored questions ───────────────────────────
/**
 * @param {string} sessionId
 * @param {number} total     Max questions to return (default 12)
 * @returns {{ questions: object[] }}
 */
export async function fetchQuestions(sessionId, total = 12) {
  try {
    const { data } = await api.get(`/questions/${sessionId}`, {
      params: { total },
    })
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

// ── 3. Score a single answer ─────────────────────────────
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

// ── 4. Get full report ────────────────────────────────────
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

// ── 5. Delete session ─────────────────────────────────────
export async function deleteSession(sessionId) {
  try {
    await api.delete(`/session/${sessionId}`)
  } catch (_) {
    // best-effort
  }
}
