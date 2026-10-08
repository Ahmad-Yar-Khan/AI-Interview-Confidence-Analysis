/**
 * ReadyScreen.jsx
 * ---------------
 * Configure screen shown after resume upload.
 * Displays a parsed-success banner, then optionally expands
 * role/JD customization before starting the interview.
 *
 * Styled to match UploadScreen — DM Serif Display + Inter, amber accent, navy base.
 */

import React, { useState } from "react";

// ─── Inject shared token system (no-op if UploadScreen already injected it) ──
const READY_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Inter:wght@400;500;600&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --navy:          #0B0F1A;
    --navy-card:     #141828;
    --navy-hover:    #1C2238;
    --amber:         #E8A838;
    --amber-dim:     rgba(232,168,56,0.10);
    --amber-glow:    rgba(232,168,56,0.22);
    --text1:         #F0EEE8;
    --text2:         #9A9589;
    --text3:         #5A5750;
    --green:         #34D399;
    --green-dim:     rgba(52,211,153,0.07);
    --green-border:  rgba(52,211,153,0.20);
    --red:           #F87171;
    --red-dim:       rgba(248,113,113,0.10);
    --border:        rgba(255,255,255,0.07);
    --border-accent: rgba(232,168,56,0.30);
    --radius:        14px;
    --radius-sm:     9px;
    --radius-pill:   100px;
    --font-display:  'DM Serif Display', Georgia, serif;
    --font-body:     'Inter', system-ui, sans-serif;
    --font-mono:     'SF Mono', 'Fira Code', monospace;
  }

  body {
    background: var(--navy);
    color: var(--text1);
    font-family: var(--font-body);
    -webkit-font-smoothing: antialiased;
    line-height: 1.5;
  }

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .rs-fade   { animation: fadeUp 0.45s ease both; }
  .rs-fade-1 { animation: fadeUp 0.45s 0.07s ease both; }
  .rs-fade-2 { animation: fadeUp 0.45s 0.14s ease both; }
  .rs-fade-3 { animation: fadeUp 0.45s 0.21s ease both; }

  .rs-spinner {
    display: inline-block;
    width: 16px; height: 16px;
    border: 2px solid rgba(255,255,255,0.15);
    border-top-color: #1A1200;
    border-radius: 50%;
    animation: spin 0.75s linear infinite;
    flex-shrink: 0;
  }

  /* ── Buttons ── */
  .rs-btn {
    display: inline-flex; align-items: center; justify-content: center;
    gap: 8px; border: none; cursor: pointer;
    font-family: var(--font-body); font-weight: 500;
    border-radius: var(--radius-pill);
    transition: all 0.18s ease;
    letter-spacing: 0.01em;
  }
  .rs-btn:disabled { opacity: 0.45; cursor: not-allowed; }

  .rs-btn-primary {
    background: var(--amber);
    color: #1A1200;
    padding: 13px 32px;
    font-size: 0.95rem;
    min-width: 180px;
    box-shadow: 0 2px 20px var(--amber-glow);
  }
  .rs-btn-primary:not(:disabled):hover {
    background: #f0b84a;
    box-shadow: 0 4px 28px rgba(232,168,56,0.35);
    transform: translateY(-1px);
  }
  .rs-btn-primary:not(:disabled):active { transform: translateY(0); }

  /* ── Card ── */
  .rs-card {
    background: var(--navy-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
  }

  /* ── Toggle button row ── */
  .rs-toggle {
    width: 100%; display: flex; align-items: center;
    justify-content: space-between;
    background: none; border: none; cursor: pointer;
    padding: 15px 20px;
    color: var(--text1);
    font-family: var(--font-body);
    font-size: 0.88rem; font-weight: 600;
    transition: background 0.15s;
  }
  .rs-toggle:hover { background: var(--navy-hover); }
  .rs-toggle-open  { border-bottom: 1px solid var(--border); }

  /* ── Inputs ── */
  .rs-input {
    width: 100%;
    background: var(--navy);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 10px 13px;
    color: var(--text1);
    font-family: var(--font-body);
    font-size: 0.88rem;
    outline: none;
    transition: border-color 0.18s;
  }
  .rs-input::placeholder { color: var(--text3); }
  .rs-input:focus { border-color: var(--amber); }

  textarea.rs-input {
    resize: vertical;
    line-height: 1.6;
    min-height: 120px;
  }

  /* ── Divider ── */
  .rs-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border), transparent);
    margin: 28px 0;
  }

  @media (prefers-reduced-motion: reduce) {
    .rs-fade, .rs-fade-1, .rs-fade-2, .rs-fade-3 { animation: none; opacity: 1; }
  }
`;

function ReadyStyles() {
  React.useEffect(() => {
    if (document.getElementById("ready-screen-styles")) return;
    const tag = document.createElement("style");
    tag.id = "ready-screen-styles";
    tag.textContent = READY_CSS;
    document.head.appendChild(tag);
    return () => tag.remove();
  }, []);
  return null;
}

// ─── Component ───────────────────────────────────────────────────────────────
export default function ReadyScreen({ profile, onStart, loading, error }) {
  const [role, setRole] = useState("");
  const [jd, setJd] = useState("");
  const [showCustomize, setShowCustomize] = useState(false);

  if (!profile) return null;

  const hasContext = role.trim() || jd.trim();
  const wordCount = profile.char_count
    ? Math.round(profile.char_count / 5).toLocaleString()
    : null;
  const firstName = profile.name.split(" ")[0];

  return (
    <>
      <ReadyStyles />

      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "48px 24px",
          background:
            "radial-gradient(ellipse 70% 50% at 50% 0%, rgba(232,168,56,0.05) 0%, transparent 65%)",
        }}
      >
        <div style={{ maxWidth: 560, width: "100%" }}>
          {/* ── Parsed success banner ── */}
          <div
            className="rs-fade"
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 14,
              background: "var(--green-dim)",
              border: "1px solid var(--green-border)",
              borderRadius: "var(--radius-sm)",
              padding: "14px 18px",
              marginBottom: 28,
            }}
          >
            <span
              style={{
                width: 22,
                height: 22,
                flexShrink: 0,
                borderRadius: "50%",
                background: "var(--green-border)",
                border: "1px solid var(--green)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.7rem",
                color: "var(--green)",
                marginTop: 1,
              }}
            >
              ✓
            </span>
            <div>
              <div
                style={{
                  fontWeight: 600,
                  fontSize: "0.85rem",
                  color: "var(--green)",
                  marginBottom: 3,
                }}
              >
                Resume uploaded
              </div>
              <div
                style={{
                  fontSize: "0.78rem",
                  color: "var(--text2)",
                  lineHeight: 1.6,
                }}
              >
                <span style={{ color: "var(--text1)", fontWeight: 500 }}>
                  {profile.name}
                </span>
                {wordCount && <> · ~{wordCount} words extracted</>}
                {profile.filename && (
                  <span
                    style={{
                      marginLeft: 8,
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.68rem",
                      color: "var(--text3)",
                    }}
                  >
                    {profile.filename}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* ── Heading ── */}
          <div className="rs-fade-1" style={{ marginBottom: 28 }}>
            <h2
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "clamp(1.7rem, 5vw, 2.2rem)",
                lineHeight: 1.2,
                letterSpacing: "-0.02em",
                color: "var(--text1)",
                marginBottom: 10,
              }}
            >
              Ready,{" "}
              <em style={{ color: "var(--amber)", fontStyle: "italic" }}>
                {firstName}.
              </em>
            </h2>
            <p
              style={{
                color: "var(--text2)",
                fontSize: "0.88rem",
                lineHeight: 1.7,
              }}
            >
              Start now, or target a specific role below to get questions built
              around that position.
            </p>
          </div>

          {/* ── Customize accordion ── */}
          <div className="rs-card rs-fade-2" style={{ marginBottom: 24 }}>
            <button
              className={`rs-toggle${showCustomize ? " rs-toggle-open" : ""}`}
              onClick={() => setShowCustomize((v) => !v)}
              aria-expanded={showCustomize}
            >
              <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                Target a specific role
                {hasContext && (
                  <span
                    style={{
                      fontSize: "0.66rem",
                      fontFamily: "var(--font-mono)",
                      color: "var(--amber)",
                      background: "var(--amber-dim)",
                      border: "1px solid var(--border-accent)",
                      borderRadius: "var(--radius-pill)",
                      padding: "2px 8px",
                      letterSpacing: "0.04em",
                    }}
                  >
                    added
                  </span>
                )}
              </span>
              <span
                style={{
                  color: "var(--text3)",
                  fontSize: "0.75rem",
                  display: "inline-block",
                  transform: showCustomize ? "rotate(180deg)" : "none",
                  transition: "transform 0.2s ease",
                }}
              >
                ▾
              </span>
            </button>

            {showCustomize && (
              <div style={{ padding: "20px 20px 22px" }}>
                {/* Role input */}
                <label style={{ display: "block", marginBottom: 14 }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: 8,
                      marginBottom: 6,
                    }}
                  >
                    <span
                      style={{
                        fontWeight: 600,
                        fontSize: "0.83rem",
                        color: "var(--text1)",
                      }}
                    >
                      Job title
                    </span>
                    <span
                      style={{
                        fontSize: "0.68rem",
                        fontFamily: "var(--font-mono)",
                        color: "var(--text3)",
                      }}
                    >
                      optional
                    </span>
                  </div>
                  <input
                    type="text"
                    className="rs-input"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    placeholder="e.g. Senior Backend Engineer at Google"
                    maxLength={120}
                  />
                </label>

                {/* JD textarea */}
                <label style={{ display: "block" }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: 8,
                      marginBottom: 6,
                    }}
                  >
                    <span
                      style={{
                        fontWeight: 600,
                        fontSize: "0.83rem",
                        color: "var(--text1)",
                      }}
                    >
                      Job description
                    </span>
                    <span
                      style={{
                        fontSize: "0.68rem",
                        fontFamily: "var(--font-mono)",
                        color: "var(--text3)",
                      }}
                    >
                      optional
                    </span>
                  </div>
                  <textarea
                    className="rs-input"
                    value={jd}
                    onChange={(e) => setJd(e.target.value)}
                    placeholder="Paste the job description here — your questions will be tailored to it."
                    rows={6}
                    maxLength={4000}
                  />
                  {jd.length > 3500 && (
                    <div
                      style={{
                        fontSize: "0.7rem",
                        color: "var(--text3)",
                        fontFamily: "var(--font-mono)",
                        marginTop: 5,
                        textAlign: "right",
                      }}
                    >
                      {jd.length} / 4000
                    </div>
                  )}
                </label>

                {hasContext && (
                  <div
                    style={{
                      marginTop: 16,
                      background: "var(--amber-dim)",
                      border: "1px solid var(--border-accent)",
                      borderRadius: "var(--radius-sm)",
                      padding: "11px 14px",
                      fontSize: "0.78rem",
                      color: "var(--text2)",
                      lineHeight: 1.6,
                    }}
                  >
                    <span style={{ color: "var(--amber)", fontWeight: 600 }}>
                      Role context set —{" "}
                    </span>
                    your questions will be tailored to this position and your
                    experience.
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── Error ── */}
          {error && (
            <div
              style={{
                marginBottom: 20,
                background: "var(--red-dim)",
                border: "1px solid rgba(248,113,113,0.22)",
                borderRadius: "var(--radius-sm)",
                padding: "12px 16px",
                color: "var(--red)",
                fontSize: "0.83rem",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <span aria-hidden="true">⚠</span>
              {error}
            </div>
          )}

          {/* ── CTA ── */}
          <div
            className="rs-fade-3"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              flexWrap: "wrap",
            }}
          >
            <button
              className="rs-btn rs-btn-primary"
              onClick={() => onStart(role, jd)}
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="rs-spinner" />
                  Generating questions…
                </>
              ) : hasContext ? (
                "Start interview →"
              ) : (
                "Start interview →"
              )}
            </button>
            {!loading && (
              <span
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text3)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                ~24–48 sec
              </span>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
