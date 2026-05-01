/**
 * useInterview.js
 * ---------------
 * Central state hook. Manages: upload → parse → select → interview → report.
 * Handles both technical questions (has_answer=true) and HR behavioral (has_answer=false).
 */

import { useState, useCallback } from 'react'
import {
  uploadResume, fetchQuestions, scoreAnswer, fetchReport, deleteSession,
  submitConfidence as submitConfidenceApi,
} from '../utils/api'

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

  const clearError = () => setError(null)

  // ── 1. Upload & Parse ────────────────────────────────────
  const handleUpload = useCallback(async (file) => {
    setLoading(true); setError(null)
    try {
      const result  = await uploadResume(file)
      const sid     = result.session_id
      const prof    = result.profile

      setSessionId(sid)
      setProfile(prof)

      const qResult = await fetchQuestions(sid, 12)
      setQuestions(qResult.questions)
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
  const startInterview = useCallback(() => {
    setCurrentIndex(0)
    setStep('interview')
  }, [])

  // ── 3. Submit Answer ─────────────────────────────────────
  const submitAnswer = useCallback(async (userAnswer, replayCount = 0, audioBlob = null) => {
    const q = questions[currentIndex]
    if (!q || !sessionId) return
    setLoading(true); setError(null)
    try {
      const result = await scoreAnswer({
        session_id:    sessionId,
        question_id:   q.id,
        question_text: q.question,
        model_answer:  q.answer,        // null for HR questions
        user_answer:   userAnswer,
        category:      q.category,
        difficulty:    q.difficulty,
        has_answer:    q.has_answer,    // false for HR & Behavioral
      })
      setAnswers(prev => ({
        ...prev,
        [q.id]: {
          userAnswer,
          modelAnswer:   q.answer,
          overall:       result.overall,
          is_behavioral: result.is_behavioral,
          angles:        result.angles,
          replayCount,
        },
      }))

      // Fire confidence analysis in background (non-blocking)
      if (audioBlob) {
        const qid = q.id
        setConfidenceScores(prev => ({
          ...prev,
          [qid]: { status: 'pending', label: null, probability: null, score: null },
        }))
        submitConfidenceApi(audioBlob)
          .then(r => {
            setConfidenceScores(prev => ({
              ...prev,
              [qid]: {
                status:      'done',
                label:       r.predicted_label,
                probability: r.confidence_probability,
                score:       r.confidence_score_1_to_10,
              },
            }))
          })
          .catch(() => {
            setConfidenceScores(prev => ({
              ...prev,
              [qid]: { status: 'failed', label: null, probability: null, score: null },
            }))
          })
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [questions, currentIndex, sessionId])

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
    setAnswers({}); setConfidenceScores({}); setCurrentIndex(0); setReport(null); setStep('interview')
  }, [])

  // ── Derived ───────────────────────────────────────────────
  const currentQuestion = questions[currentIndex] || null
  const currentAnswer   = currentQuestion ? answers[currentQuestion.id] : null
  const answeredCount   = Object.keys(answers).length
  const allAnswered     = questions.length > 0 && answeredCount >= questions.length
  const progress        = questions.length > 0 ? (answeredCount / questions.length) * 100 : 0

  return {
    step, loading, error,
    sessionId, profile, questions,
    currentIndex, currentQuestion, currentAnswer,
    answers, answeredCount, allAnswered, progress,
    confidenceScores,
    report,
    handleUpload, startInterview, submitAnswer,
    goNext, goPrev,
    showReport, reset, retake, clearError,
  }
}
