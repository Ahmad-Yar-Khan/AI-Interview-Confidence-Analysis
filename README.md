# Smart Interview — Full Stack App

AI-powered interview prep that parses any resume, selects tailored questions from a Kaggle dataset using TF-IDF vector embeddings + FAISS similarity search, records answers, and scores them across multiple semantic angles.

---

## Project Structure

```
smart-interview/
├── backend/
│   ├── main.py                  # FastAPI entry point
│   ├── resume_parser.py         # PDF/DOCX resume parser
│   ├── embedding_engine.py      # TF-IDF vectorizer + FAISS index
│   ├── question_selector.py     # Resume-aware question ranking
│   ├── scorer.py                # Multi-angle answer scoring
│   ├── data_loader.py           # Kaggle CSV loader + preprocessor
│   ├── requirements.txt
│   └── data/
│       └── new_interview_questions.csv   ← place Kaggle CSV here
│
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── index.css
│   │   ├── components/
│   │   │   ├── UploadScreen.jsx
│   │   │   ├── ProfileStrip.jsx
│   │   │   ├── InterviewScreen.jsx
│   │   │   ├── ScoreBlock.jsx
│   │   │   └── ReportScreen.jsx
│   │   ├── utils/
│   │   │   └── api.js           # Axios calls to backend
│   │   └── hooks/
│   │       └── useInterview.js  # Global state hook
│   └── package.json
│
└── README.md
```

---

## Quick Start

### 1. Place the dataset
```
backend/data/new_interview_questions.csv
```

### 2. Backend (Python 3.9+)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Frontend (Node 18+)
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## How It Works

1. **Upload** — User uploads PDF or DOCX resume
2. **Parse** — `resume_parser.py` extracts name, title, skills, experience, projects using regex + spaCy NER
3. **Embed** — `embedding_engine.py` builds TF-IDF vectors for resume text + all questions; indexes into FAISS
4. **Select** — `question_selector.py` runs cosine similarity between resume vector and question vectors, ranks by category weight + difficulty
5. **Answer** — User types answers in the React UI
6. **Score** — `scorer.py` embeds user answer + model answer, computes similarity across 3 angles (conceptual, technical, completeness)
7. **Report** — Per-question scores + overall report with category breakdown

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/parse-resume` | Upload PDF/DOCX → returns parsed profile |
| GET | `/api/questions/{session_id}` | Get tailored question list |
| POST | `/api/score` | Score a single answer |
| GET | `/api/report/{session_id}` | Full session report |

---

## Environment Variables (optional)
```env
# backend/.env
CORS_ORIGINS=http://localhost:5173
MAX_QUESTIONS=12
DATA_PATH=data/new_interview_questions.csv
```
