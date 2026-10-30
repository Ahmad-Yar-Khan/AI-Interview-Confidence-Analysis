/**
 * useInterview.js
 * ---------------
 * Central state hook. Manages: upload → parse → select → interview → report.
 * The interview starts with a handful of generated questions; a weak score can
 * add a follow-up, which is slotted in a little after the user's current position.
 */

import { useState, useCallback, useRef } from 'react'
import {
  uploadResume, fetchQuestions, scoreAnswer, requestFollowup, fetchReport, deleteSession,
  submitConfidence as submitConfidenceApi,
} from '../api/client'

// A follow-up is placed this many slots (at most) beyond the earliest allowed
// position, chosen at random — the score arrives late, so the user has often
// already moved on and the follow-up lands after a question or two.
const FOLLOWUP_MAX_DELAY = 2

export function useInterview() {
  const [step,             setStep]             = useState('upload')
  const [loading,          setLoading]          = useState(false)
  const [error,            setError]            = useState(null)
  const [sessionId,        setSessionId]        = useState(null)
  const [profile,          setProfile]          = useState(null)
  const [questions,        setQuestions]        = useState([])
  const [currentIndex,     setCurrentIndex]     = useState(0)
  // answers: { [questionId]: { userAnswer, modelAnswer, overall, is_behavioral, angles, replayCount } }
  const [answers,          setAnswers]          = useState({})
  // confidenceScores: { [questionId]: { status, label, probability, score } }
  const [confidenceScores, setConfidenceScores] = useState({})
  const [report,           setReport]           = useState(null)
  // Number of weak answers whose follow-up request is still in flight.
  const [followupsPending, setFollowupsPending] = useState(0)
  // Latest index, readable from async callbacks that outlive a render.
  const currentIndexRef = useRef(0)
  currentIndexRef.current = currentIndex

  const clearError = () => setError(null)

  // ── 1. Upload & Parse ────────────────────────────────────
  const handleUpload = useCallback(async (file) => {
    setLoading(true); setError(null)
    try {
      const result = await uploadResume(file)
      setSessionId(result.session_id)
      setProfile(result.profile)
      setQuestions([])
      setCurrentIndex(0)
      setAnswers({})
      setReport(null)
      setStep('ready')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  // ── 2. Start Interview ───────────────────────────────────
  const startInterview = useCallback(async (role = 'other', years = null) => {
    if (!sessionId) return
    setLoading(true); setError(null)
    try {
      const qResult = await fetchQuestions(sessionId, 5, role, years)
      setQuestions(qResult.questions)
      setCurrentIndex(0)
      setAnswers({})
      setConfidenceScores({})
      setReport(null)
      setStep('interview')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  // ── Follow-ups ───────────────────────────────────────────
  // Insert after the parent AND after wherever the user is now, never behind
  // them; within the next few slots, picked at random.
  const insertFollowup = useCallback((followup) => {
    const roll = Math.random()   // outside the updater so it stays pure
    setQuestions(prev => {
      if (prev.some(x => x.id === followup.id)) return prev
      const parentIdx = prev.findIndex(x => x.id === followup.parent_id)
      const earliest  = Math.max(currentIndexRef.current, parentIdx) + 1
      const latest    = Math.min(prev.length, earliest + FOLLOWUP_MAX_DELAY)
      const at        = earliest + Math.floor(roll * (latest - earliest + 1))
      return [...prev.slice(0, at), followup, ...prev.slice(at)]
    })
  }, [])

  const maybeRequestFollowup = useCallback(async (qid) => {
    setFollowupsPending(n => n + 1)
    try {
      const { followup } = await requestFollowup(sessionId, qid)
      if (followup) insertFollowup(followup)
    } catch {
      // A missing follow-up must never break the interview — just carry on.
    } finally {
      setFollowupsPending(n => n - 1)
    }
  }, [sessionId, insertFollowup])

  // ── 3. Submit Answer ─────────────────────────────────────
  const submitAnswer = useCallback((userAnswer, replayCount = 0, audioBlob = null) => {
    const q = questions[currentIndex]
    if (!q || !sessionId) return

    const qid = q.id

    // Immediately mark as answered so the UI unlocks (Next → appears now).
    // scoring:true is a placeholder — replaced when the background finishes.
    setAnswers(prev => ({
      ...prev,
      [qid]: { scoring: true, userAnswer, replayCount },
    }))
    setError(null)

    // Run confidence + Groq scoring in the background — user can navigate freely.
    ;(async () => {
      let textForScoring = userAnswer  // SR text as fallback

      if (audioBlob) {
        setConfidenceScores(prev => ({
          ...prev,
          [qid]: { status: 'pending', label: null, probability: null, score: null },
        }))
        try {
          const confResult = await submitConfidenceApi(audioBlob)
          if (confResult.transcript?.trim()) {
            textForScoring = confResult.transcript.trim()
          }
          setConfidenceScores(prev => ({
            ...prev,
            [qid]: {
              status:      'done',
              label:       confResult.predicted_label,
              probability: confResult.confidence_probability,
              score:       confResult.confidence_score_1_to_10,
            },
          }))
        } catch {
          setConfidenceScores(prev => ({
            ...prev,
            [qid]: { status: 'failed', label: null, probability: null, score: null },
          }))
        }
      }

      try {
        const result = await scoreAnswer({
          session_id:    sessionId,
          question_id:   qid,
          question_text: q.question,
          model_answer:  q.model_answer ?? null,
          user_answer:   textForScoring,
          category:      q.category,
          difficulty:    q.difficulty,
          has_answer:    q.has_answer,
        })

        setAnswers(prev => ({
          ...prev,
          [qid]: {
            scoring:       false,
            userAnswer:    textForScoring,
            modelAnswer:   q.model_answer ?? null,
            overall:       result.overall,
            is_behavioral: result.is_behavioral,
            angles:        result.angles,
            replayCount,
          },
        }))
        // Weak answer -> ask the backend for a follow-up (runs without blocking the user).
        if (result.followup_eligible) maybeRequestFollowup(qid)
      } catch (err) {
        // Remove placeholder so the user can retry this question
        setAnswers(prev => {
          const next = { ...prev }
          delete next[qid]
          return next
        })
        setError(`Scoring failed: ${err.message}`)
      }
    })()
  }, [questions, currentIndex, sessionId, maybeRequestFollowup])

  // ── 4. Navigate ───────────────────────────────────────────
  const goNext = useCallback(() => {
    if (currentIndex < questions.length - 1) setCurrentIndex(i => i + 1)
  }, [currentIndex, questions.length])

  const goPrev = useCallback(() => {
    if (currentIndex > 0) setCurrentIndex(i => i - 1)
  }, [currentIndex])

  // ── 5. Report ─────────────────────────────────────────────
  const showReport = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const r = await fetchReport(sessionId)
      setReport(r)
      setStep('report')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  // ── 6. Reset ──────────────────────────────────────────────
  const reset = useCallback(async () => {
    if (sessionId) await deleteSession(sessionId)
    setStep('upload'); setSessionId(null); setProfile(null)
    setQuestions([]); setCurrentIndex(0); setAnswers({})
    setConfidenceScores({}); setReport(null); setError(null)
  }, [sessionId])

  // ── 7. Retake ─────────────────────────────────────────────
  const retake = useCallback(() => {
    setQuestions(qs => qs.filter(q => !q.is_followup))
    setAnswers({}); setConfidenceScores({}); setCurrentIndex(0); setReport(null); setStep('interview')
  }, [])

  // ── Derived ───────────────────────────────────────────────
  const currentQuestion  = questions[currentIndex] || null
  const currentAnswer    = currentQuestion ? answers[currentQuestion.id] : null
  const answeredCount    = Object.keys(answers).length
  const allAnswered      = questions.length > 0 && answeredCount >= questions.length
  const progress         = questions.length > 0 ? (answeredCount / questions.length) * 100 : 0
  // Counts follow-ups still being requested too: the report must wait for them,
  // otherwise "View Report" could appear just before a follow-up is added.
  const hasPendingScores = followupsPending > 0 || Object.values(answers).some(a => a.scoring === true)

  return {
    step, loading, error,
    sessionId, profile, questions,
    currentIndex, currentQuestion, currentAnswer,
    answers, answeredCount, allAnswered, progress,
    hasPendingScores,
    confidenceScores,
    report,
    handleUpload, startInterview, submitAnswer,
    goNext, goPrev,
    showReport, reset, retake, clearError,
  }
}
