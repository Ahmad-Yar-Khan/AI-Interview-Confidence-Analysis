/**
 * App.jsx
 * -------
 * Root component. Wires the useInterview hook to all screen components.
 * Flow: upload → ready → interview → report
 */

import React, { useState, useEffect, useRef } from "react";
import { useInterview } from "./hooks/useInterview";

import UploadScreen from "./screens/UploadScreen";
import ProfileStrip from "./components/ProfileStrip";
import ReadyScreen from "./screens/ReadyScreen";
import InterviewScreen from "./screens/InterviewScreen";
import ReportScreen from "./screens/ReportScreen";
import ConfidenceTestPage from "./screens/ConfidenceTestPage";
import QuestionsPage from "./screens/QuestionsPage";

// ── Loading screen quotes ─────────────────────────────────
const QUESTION_QUOTES = [
  {
    text: "The secret of getting ahead is getting started.",
    author: "Mark Twain",
  },
  { text: "You've prepared for this. Trust yourself.", author: null },
  {
    text: "Interview jitters? That's just excitement doing its job.",
    author: null,
  },
  { text: "Every expert was once a beginner.", author: null },
  {
    text: "You're not just answering questions — you're telling your story.",
    author: null,
  },
  {
    text: "Confidence isn't always being right. It's not fearing to be wrong.",
    author: null,
  },
];
const REPORT_QUOTES = [
  { text: "Win or learn — there's no losing here.", author: null },
  { text: "Every answer you gave was a step forward.", author: null },
  { text: "Self-awareness is the first step to mastery.", author: null },
  { text: "The courage to show up is already half the battle.", author: null },
  { text: "Growth happens in the moments you push through.", author: null },
  {
    text: "Your next interview will be sharper because of this one.",
    author: null,
  },
];

function LoadingScreen({ mode }) {
  const quotes = mode === "report" ? REPORT_QUOTES : QUESTION_QUOTES;
  const [qi, setQi] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const t = setInterval(() => {
      setVisible(false);
      const swap = setTimeout(() => {
        setQi((i) => (i + 1) % quotes.length);
        setVisible(true);
      }, 350);
      return () => clearTimeout(swap);
    }, 3800);
    return () => clearInterval(t);
  }, [quotes.length]);

  const q = quotes[qi];
  const isReport = mode === "report";
  const color = isReport ? "var(--green)" : "var(--accent)";

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "var(--bg)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 200,
        padding: "0 24px",
      }}
    >
      <style>{`
        @keyframes ls-wave {
          0%, 100% { transform: scaleY(0.3); }
          50%       { transform: scaleY(1); }
        }
        @keyframes ls-shimmer {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(400%); }
        }
        @keyframes ls-float {
          0%, 100% { transform: translateY(0px); }
          50%       { transform: translateY(-6px); }
        }
      `}</style>

      <div
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: "1.1rem",
          letterSpacing: "-0.02em",
          color: "var(--text2)",
          marginBottom: 52,
          opacity: 0.65,
        }}
      >
        Smart<span style={{ color: "var(--accent)" }}>Interview</span>
      </div>

      <div
        style={{
          display: "flex",
          gap: 5,
          alignItems: "center",
          height: 52,
          marginBottom: 36,
          animation: "ls-float 3.2s ease-in-out infinite",
        }}
      >
        {[0.4, 0.65, 0.9, 1, 0.75, 1, 0.85, 0.6, 0.9, 0.5, 0.7, 0.45].map(
          (h, i) => (
            <div
              key={i}
              style={{
                width: 5,
                borderRadius: 3,
                background: color,
                height: `${h * 100}%`,
                animation: `ls-wave ${0.8 + i * 0.07}s ease-in-out infinite`,
                animationDelay: `${i * 0.08}s`,
                opacity: 0.8,
              }}
            />
          ),
        )}
      </div>

      <div
        style={{
          fontSize: "1.3rem",
          fontWeight: 700,
          color: "var(--text)",
          marginBottom: 10,
          textAlign: "center",
          letterSpacing: "-0.02em",
        }}
      >
        {isReport ? "Compiling Your Results" : "Crafting Your Interview"}
      </div>

      <div
        style={{
          fontSize: "0.84rem",
          color: "var(--text2)",
          marginBottom: 44,
          textAlign: "center",
          lineHeight: 1.6,
          maxWidth: 360,
        }}
      >
        {isReport
          ? "Reviewing your answers and preparing your detailed feedback…"
          : "Analyzing your resume and personalizing your questions…"}
      </div>

      <div
        style={{
          width: 260,
          height: 2,
          background: "var(--border)",
          borderRadius: 99,
          overflow: "hidden",
          marginBottom: 52,
          position: "relative",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: 0,
            bottom: 0,
            width: "40%",
            background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
            animation: "ls-shimmer 1.8s ease-in-out infinite",
          }}
        />
      </div>

      <div
        style={{
          maxWidth: 440,
          textAlign: "center",
          opacity: visible ? 1 : 0,
          transition: "opacity 0.35s ease",
        }}
      >
        <div
          style={{
            fontSize: "0.92rem",
            color: "var(--text)",
            lineHeight: 1.7,
            fontStyle: "italic",
            marginBottom: 8,
          }}
        >
          "{q.text}"
        </div>
        {q.author && (
          <div style={{ fontSize: "0.72rem", color: "var(--muted)" }}>
            — {q.author}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Step indicator ────────────────────────────────────────

const STEPS = [
  { key: "upload", label: "Upload Resume" },
  { key: "ready", label: "Questions Ready" },
  { key: "interview", label: "Interview" },
  { key: "report", label: "Report" },
];
function StepIndicator({ currentStep }) {
  const idx = STEPS.findIndex((s) => s.key === currentStep);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 0,
        padding: "16px 36px",
        background: "var(--bg)",
        borderBottom: "1px solid var(--border)",
      }}
    >
      {STEPS.map((step, i) => {
        const done = i < idx;
        const active = i === idx;

        return (
          <React.Fragment key={step.key}>
            {i > 0 && (
              <div
                style={{
                  width: 36,
                  height: 1,
                  background: done ? "var(--accent)" : "var(--border)",
                  margin: "0 8px",
                  transition: "all 0.3s ease",
                }}
              />
            )}

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <div
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.78rem",
                  fontWeight: 600,
                  background: done || active ? "var(--accent)" : "transparent",
                  color: done || active ? "#fff" : "var(--muted)",
                  border: done || active ? "none" : "1px solid var(--border2)",
                  transition: "all 0.25s ease",
                  flexShrink: 0,
                }}
              >
                {done ? "✓" : i + 1}
              </div>

              <span
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: "0.85rem",
                  letterSpacing: "-0.01em",
                  color: active ? "var(--text)" : "var(--text2)",
                  fontWeight: active ? 600 : 400,
                  whiteSpace: "nowrap",
                }}
              >
                {step.label}
              </span>
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ── Top bar ───────────────────────────────────────────────
function TopBar({ onToggleConfidence, confidenceActive }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 36px",
        height: 72,
        background: "var(--bg)",
        borderBottom: "1px solid var(--border)",
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: "1.7rem",
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
          color: "var(--text)",
        }}
      >
        Smart{" "}
        <span
          style={{
            color: "var(--accent)",
            fontStyle: "italic",
          }}
        >
          Interview
        </span>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 24,
        }}
      >
        <button
          onClick={onToggleConfidence}
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: "0.9rem",
            color: confidenceActive ? "var(--accent)" : "var(--text2)",
            background: "transparent",
            border: "none",
            cursor: "pointer",
            padding: 0,
            fontStyle: confidenceActive ? "italic" : "normal",
            transition: "all 0.2s ease",
          }}
        >
          Confidence Test
        </button>

        <div
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: "0.85rem",
            color: "var(--text2)",
            fontStyle: "italic",
            letterSpacing: "-0.01em",
          }}
        >
          Personalized interview coaching
        </div>
      </div>
    </div>
  );
}
// ── App ──────────────────────────────────────────────────

export default function App() {
  const interview = useInterview();

  // Scroll to top whenever the step changes
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [interview.step]);
  const [showConfidence, setShowConfidence] = useState(
    () => window.location.hash === "#confidence-test",
  );
  const [showQuestions, setShowQuestions] = useState(
    () => window.location.hash === "#questions",
  );
  const [isLoadingReport, setIsLoadingReport] = useState(false);

  useEffect(() => {
    const handler = () => {
      setShowConfidence(window.location.hash === "#confidence-test");
      setShowQuestions(window.location.hash === "#questions");
    };
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);

  const toggleConfidence = () => {
    const next = !showConfidence;
    window.location.hash = next ? "#confidence-test" : "";
    setShowConfidence(next);
    setShowQuestions(false);
  };

  if (showConfidence) {
    return (
      <div style={{ minHeight: "100vh" }}>
        <TopBar onToggleConfidence={toggleConfidence} confidenceActive />
        <ConfidenceTestPage />
      </div>
    );
  }

  if (showQuestions) {
    return (
      <div style={{ minHeight: "100vh" }}>
        <TopBar
          onToggleConfidence={toggleConfidence}
          confidenceActive={false}
        />
        <QuestionsPage questions={interview.questions} />
      </div>
    );
  }

  const {
    step,
    loading,
    error,
    profile,
    questions,
    currentIndex,
    currentQuestion,
    currentAnswer,
    answeredCount,
    allAnswered,
    progress,
    hasPendingScores,
    confidenceScores,
    report,
    handleUpload,
    startInterview,
    submitAnswer,
    goNext,
    goPrev,
    showReport,
    reset,
    retake,
    clearError,
  } = interview;

  const handleShowReport = async () => {
    setIsLoadingReport(true);
    await showReport();
    setIsLoadingReport(false);
  };

  if (isLoadingReport) return <LoadingScreen mode="report" />;

  // Upload screen — full page, no bars
  if (step === "upload") {
    return (
      <div style={{ minHeight: "100vh" }}>
        <TopBar
          onToggleConfidence={toggleConfidence}
          confidenceActive={false}
        />
        <StepIndicator currentStep={step} />
        <UploadScreen onUpload={handleUpload} loading={loading} error={error} />
      </div>
    );
  }

  if (step === "ready" && loading) return <LoadingScreen mode="questions" />;

  // Focus mode: strip all chrome during active interview
  if (step === "interview") {
    return (
      <div style={{ minHeight: "100vh" }}>
        <InterviewScreen
          questions={questions}
          currentIndex={currentIndex}
          currentQuestion={currentQuestion}
          currentAnswer={currentAnswer}
          answeredCount={answeredCount}
          allAnswered={allAnswered}
          progress={progress}
          hasPendingScores={hasPendingScores}
          loading={loading}
          error={error}
          onSubmit={submitAnswer}
          onNext={goNext}
          onPrev={goPrev}
          onShowReport={handleShowReport}
          onClearError={clearError}
        />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <TopBar onToggleConfidence={toggleConfidence} confidenceActive={false} />
      <StepIndicator currentStep={step} />
      <ProfileStrip profile={profile} onReset={reset} />

      <div style={{ flex: 1 }}>
        {step === "ready" && (
          <ReadyScreen
            profile={profile}
            onStart={startInterview}
            loading={loading}
            error={error}
          />
        )}

        {step === "report" && (
          <ReportScreen
            report={report}
            confidenceScores={confidenceScores}
            onRetake={retake}
            onReset={reset}
          />
        )}
      </div>
    </div>
  );
}
