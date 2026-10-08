/**
 * UploadScreen.jsx — Redesigned
 * First screen of SmartInterview.
 * Accepts PDF, DOCX, TXT. No tech jargon.
 */

import React, { useCallback, useState, useEffect, useRef } from "react";
import { useDropzone } from "react-dropzone";

const ACCEPTED = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
    ".docx",
  ],
  "text/plain": [".txt"],
};

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

// ─── Inline global styles (injected once) ────────────────────────────────────
const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Inter:wght@400;500;600&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --navy:       #0B0F1A;
    --navy-card:  #141828;
    --navy-hover: #1C2238;
    --amber:     #E8A838;
    --amber-dim: rgba(232,168,56,0.10);
    --amber-glow:rgba(232,168,56,0.22);
    --text1:      #F0EEE8;
    --text2:      #9A9589;
    --text3:      #5A5750;
    --red:        #F87171;
    --red-dim:    rgba(248,113,113,0.10);
    --border:     rgba(255,255,255,0.07);
    --border-accent: rgba(232,168,56,0.30);
    --radius:     14px;
    --radius-sm:  9px;
    --radius-pill:100px;
    --font-display:'DM Serif Display', Georgia, serif;
    --font-body:  'Inter', system-ui, sans-serif;
    --font-mono:  'SF Mono','Fira Code',monospace;
  }

  body {
    background: var(--navy);
    color: var(--text1);
    font-family: var(--font-body);
    -webkit-font-smoothing: antialiased;
    line-height: 1.5;
  }

  /* ── Animations ── */
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(18px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes pulse-ring {
    0%,100% { box-shadow: 0 0 0 0 var(--amber-glow); }
    50%      { box-shadow: 0 0 0 12px transparent; }
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  @keyframes dotBounce {
    0%,80%,100% { transform: translateY(0); opacity: 0.4; }
    40%         { transform: translateY(-6px); opacity: 1; }
  }

  .fade-up { animation: fadeUp 0.5s ease both; }
  .fade-up-1 { animation: fadeUp 0.5s 0.08s ease both; }
  .fade-up-2 { animation: fadeUp 0.5s 0.16s ease both; }
  .fade-up-3 { animation: fadeUp 0.5s 0.24s ease both; }

  /* ── Spinner ── */
  .spinner {
    width: 28px; height: 28px;
    border: 2px solid var(--border);
    border-top-color: var(--amber);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  /* ── Dot pulse ── */
  .dots { display: flex; gap: 5px; align-items: center; }
  .dots span {
    width: 5px; height: 5px; border-radius: 50%;
    background: var(--amber); display: inline-block;
    animation: dotBounce 1.2s ease infinite;
  }
  .dots span:nth-child(2) { animation-delay: 0.15s; }
  .dots span:nth-child(3) { animation-delay: 0.30s; }

  /* ── Buttons ── */
  .btn {
    display: inline-flex; align-items: center; justify-content: center;
    gap: 8px; border: none; cursor: pointer;
    font-family: var(--font-body); font-weight: 500;
    border-radius: var(--radius-pill);
    transition: all 0.18s ease;
    letter-spacing: 0.01em;
    text-decoration: none;
  }
  .btn:disabled { opacity: 0.45; cursor: not-allowed; }

  .btn-primary {
    background: var(--amber);
    color: #fff;
    padding: 13px 28px;
    font-size: 0.95rem;
    box-shadow: 0 2px 20px var(--amber-glow);
  }
  .btn-primary:not(:disabled):hover {
    background: #f0b84a;
    box-shadow: 0 4px 28px rgba(232,168,56,0.35);
    transform: translateY(-1px);
  }
  .btn-primary:not(:disabled):active { transform: translateY(0); }

  .btn-ghost {
    background: transparent;
    color: var(--text2);
    border: 1px solid var(--border);
    padding: 8px 16px;
    font-size: 0.82rem;
  }
  .btn-ghost:hover { background: var(--navy-hover); color: var(--text1); border-color: rgba(255,255,255,0.14); }

  /* ── Dropzone ring ── */
  .dropzone-stage {
    position: relative;
    border-radius: 50%;
    width: 240px; height: 240px;
    margin: 0 auto;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    transition: transform 0.25s ease;
    outline: none;
  }
  .dropzone-stage::before {
    content: '';
    position: absolute; inset: 0;
    border-radius: 50%;
    border: 2px dashed var(--text3);
    transition: border-color 0.25s ease, box-shadow 0.25s ease;
  }
  .dropzone-stage:hover::before,
  .dropzone-stage:focus::before {
    border-color: var(--amber);
    box-shadow: 0 0 0 6px var(--amber-dim);
  }
  .dropzone-stage.active::before {
    border-color: var(--amber);
    box-shadow: 0 0 0 8px var(--amber-dim);
    animation: pulse-ring 1.4s ease infinite;
  }
  .dropzone-stage.active { transform: scale(1.04); }

  /* ── File ready card ── */
  .file-card {
    border: 1px solid var(--border-accent);
    border-radius: var(--radius);
    background: var(--navy-card);
    padding: 24px;
    box-shadow: 0 0 0 1px var(--amber-dim), 0 8px 32px rgba(0,0,0,0.4);
  }

  /* ── Outcome pills ── */
  .outcome-list {
    display: flex; flex-wrap: wrap;
    gap: 10px; justify-content: center;
    margin-top: 40px;
  }
  .outcome-pill {
    display: inline-flex; align-items: center; gap: 7px;
    background: var(--navy-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-pill);
    padding: 8px 16px;
    font-size: 0.78rem;
    color: var(--text2);
    letter-spacing: 0.01em;
  }
  .outcome-pill .dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--amber); flex-shrink: 0;
    box-shadow: 0 0 6px var(--amber);
  }

  /* ── Error ── */
  .error-banner {
    background: var(--red-dim);
    border: 1px solid rgba(248,113,113,0.22);
    border-radius: var(--radius-sm);
    padding: 12px 16px;
    color: var(--red);
    font-size: 0.84rem;
    margin-top: 16px;
    display: flex; align-items: center; gap: 8px;
  }

  /* ── Divider ── */
  .divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border), transparent);
    margin: 36px 0;
  }

  /* ── Responsive ── */
  @media (max-width: 480px) {
    .dropzone-stage { width: 200px; height: 200px; }
    .outcome-list { gap: 8px; }
  }

  @media (prefers-reduced-motion: reduce) {
    .fade-up, .fade-up-1, .fade-up-2, .fade-up-3 { animation: none; opacity: 1; }
    .dropzone-stage.active::before { animation: none; }
  }
`;

function GlobalStyles() {
  useEffect(() => {
    if (document.getElementById("upload-screen-styles")) return;
    const tag = document.createElement("style");
    tag.id = "upload-screen-styles";
    tag.textContent = GLOBAL_CSS;
    document.head.appendChild(tag);
    return () => tag.remove();
  }, []);
  return null;
}

// ─── Component ───────────────────────────────────────────────────────────────
export default function UploadScreen({ onUpload, loading, error }) {
  const [file, setFile] = useState(null);
  const [localError, setLocalError] = useState("");
  const fileCardRef = useRef(null);

  useEffect(() => {
    if (file && fileCardRef.current) {
      fileCardRef.current.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  }, [file]);

  const onDrop = useCallback((accepted, rejected) => {
    setLocalError("");
    if (rejected.length > 0) {
      setLocalError(
        "That file type isn't supported. Please upload a PDF, DOCX, or TXT file.",
      );
      return;
    }
    if (accepted.length > 0) {
      const f = accepted[0];
      if (f.size > 10 * 1024 * 1024) {
        setLocalError("File is too large. The maximum size is 10 MB.");
        return;
      }
      setFile(f);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxFiles: 1,
    disabled: loading || !!file,
  });

  const displayError = localError || error;

  const fileExt = file?.name.split(".").pop().toUpperCase() ?? "";

  return (
    <>
      <GlobalStyles />

      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "48px 24px",
          // Subtle radial glow behind the hero
          background:
            "radial-gradient(ellipse 70% 50% at 50% 0%, rgba(232,168,56,0.05) 0%, transparent 65%)",
        }}
      >
        <div style={{ maxWidth: 520, width: "100%" }}>
          {/* ── Wordmark ── */}
          <div
            className="fade-up"
            style={{
              textAlign: "center",
              marginBottom: 48,
            }}
          >
            <p
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "0.7rem",
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--amber)",
                marginBottom: 14,
              }}
            >
              Smart Interview
            </p>
            <h1
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "clamp(2rem, 6vw, 2.9rem)",
                lineHeight: 1.15,
                letterSpacing: "-0.02em",
                color: "var(--text1)",
              }}
            >
              Your resume,
              <br />
              <em style={{ color: "var(--amber)", fontStyle: "italic" }}>
                your interview.
              </em>
            </h1>
            <p
              style={{
                marginTop: 14,
                color: "var(--text2)",
                fontSize: "0.9rem",
                lineHeight: 1.7,
                maxWidth: 380,
                margin: "14px auto 0",
              }}
            >
              Upload your resume and get interview questions crafted around your
              actual experience — not a generic template.
            </p>
          </div>

          {/* ── Drop stage (hidden once file is selected or loading) ── */}
          {!file && !loading && (
            <div className="fade-up-1" style={{ textAlign: "center" }}>
              <div
                {...getRootProps()}
                className={`dropzone-stage${isDragActive ? " active" : ""}`}
              >
                <input {...getInputProps()} />
                <div style={{ pointerEvents: "none", userSelect: "none" }}>
                  <div
                    style={{
                      fontSize: isDragActive ? "2.8rem" : "2.2rem",
                      marginBottom: 10,
                      transition: "font-size 0.2s ease",
                      lineHeight: 1,
                    }}
                  >
                    {isDragActive ? "📂" : "📄"}
                  </div>
                  <div
                    style={{
                      fontFamily: "var(--font-display)",
                      fontSize: "1.05rem",
                      color: "var(--text1)",
                      marginBottom: 4,
                    }}
                  >
                    {isDragActive ? "Let go to upload" : "Drop here"}
                  </div>
                  <div
                    style={{
                      fontSize: "0.73rem",
                      color: "var(--text3)",
                    }}
                  >
                    or click to browse
                  </div>
                </div>
              </div>

              <p
                style={{
                  marginTop: 18,
                  fontSize: "0.72rem",
                  color: "var(--text3)",
                  letterSpacing: "0.04em",
                }}
              >
                PDF · DOCX · TXT &nbsp;·&nbsp; max 10 MB
              </p>
            </div>
          )}

          {/* ── File selected card ── */}
          {file && !loading && (
            <div ref={fileCardRef} className="file-card fade-up">
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  marginBottom: 22,
                }}
              >
                {/* File type badge */}
                <div
                  style={{
                    width: 44,
                    height: 44,
                    flexShrink: 0,
                    background: "var(--amber-dim)",
                    border: "1px solid var(--border-accent)",
                    borderRadius: 10,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.6rem",
                    fontWeight: 600,
                    color: "var(--amber)",
                    letterSpacing: "0.05em",
                  }}
                >
                  {fileExt}
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontWeight: 600,
                      fontSize: "0.9rem",
                      color: "var(--text1)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      marginBottom: 3,
                    }}
                  >
                    {file.name}
                  </div>
                  <div
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text2)",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    {formatBytes(file.size)}
                  </div>
                </div>

                <button
                  className="btn btn-ghost"
                  onClick={() => {
                    setFile(null);
                    setLocalError("");
                  }}
                  aria-label="Remove file"
                >
                  Change
                </button>
              </div>

              <button
                className="btn btn-primary"
                style={{ width: "100%" }}
                onClick={() => onUpload(file)}
              >
                Start my interview →
              </button>
            </div>
          )}

          {/* ── Loading state ── */}
          {loading && (
            <div
              className="fade-up"
              style={{ textAlign: "center", padding: "12px 0" }}
            >
              <div className="spinner" style={{ margin: "0 auto 16px" }} />
              <p
                style={{
                  color: "var(--text2)",
                  fontSize: "0.88rem",
                  marginBottom: 14,
                }}
              >
                Reading your resume…
              </p>
              <div className="dots" style={{ justifyContent: "center" }}>
                <span />
                <span />
                <span />
              </div>
            </div>
          )}

          {/* ── Error ── */}
          {displayError && !loading && (
            <div className="error-banner fade-up" role="alert">
              <span aria-hidden="true">⚠</span>
              {displayError}
            </div>
          )}

          {/* ── Divider ── */}
          {!loading && (
            <div className="divider" style={{ marginTop: file ? 36 : 32 }} />
          )}

          {/* ── Outcome pills ── */}
          {!loading && (
            <div className="fade-up-2 outcome-list">
              {[
                "Questions tailored to your background",
                "Covers every role on your resume",
                "Scored feedback after each answer",
              ].map((text) => (
                <span key={text} className="outcome-pill">
                  <span className="dot" aria-hidden="true" />
                  {text}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
