
# 🤖 SmartInterview: AI-Driven Recruitment & Evaluation Pipeline

**SmartInterview** is a sophisticated Full-Stack RAG (Retrieval-Augmented Generation) application designed to automate the technical interview process. By leveraging **TF-IDF vector embeddings** and **FAISS similarity search**, the system parses resumes and dynamically retrieves the most relevant technical questions from a Kaggle-sourced dataset, providing a personalized and mathematically-grounded evaluation of a candidate's performance.

---

## 🚀 Core Technical Features

### 1. Intelligence Engine (The RAG Pipeline)
* **Resume Parsing:** Uses **spaCy NER** and RegEx to extract high-fidelity entities (Skills, Projects, Experience) from PDF/DOCX.
* **Vector Space Indexing:** Implements **TF-IDF Vectorization** to transform raw text into numerical features.
* **Efficient Retrieval:** Utilizes **FAISS (Facebook AI Similarity Search)** to perform high-speed K-Nearest Neighbor searches, matching candidate profiles to specific question clusters.

### 2. Multi-Angle Evaluation (The Scorer)
The `scorer.py` module doesn't just check for keywords; it computes a **Cosine Similarity** score across three distinct semantic dimensions:
* **Conceptual:** Accuracy of the core principles mentioned.
* **Technical:** Presence of domain-specific terminology and syntax.
* **Completeness:** The breadth of the answer relative to the model solution.

### 3. Speech & Confidence Analytics (Future-Ready)
* Integrates signal processing hooks to evaluate **Speech Features** (fluency, pitch, and rate) to determine a candidate's **Confidence Score**.

---

## 📂 Project Architecture

```text
smart-interview/
├── backend/                # FastAPI Microservice
│   ├── main.py             # Entry point & API Routing
│   ├── resume_parser.py    # spaCy-based extraction engine
│   ├── embedding_engine.py # TF-IDF + FAISS Indexing
│   ├── scorer.py           # Triple-angle semantic scoring
│   └── data/               # Kaggle Dataset Storage
├── frontend/               # React + Vite Application
│   ├── src/
│   │   ├── components/     # Atomic UI components (Upload, Interview, Report)
│   │   ├── hooks/          # Custom state management (useInterview)
│   │   └── utils/          # Axios-based API abstraction
└── README.md
```

---

## 🛠️ Tech Stack

* **Frontend:** React (Vite), Tailwind CSS, Axios.
* **Backend:** FastAPI (Python 3.9+).
* **NLP/AI:** spaCy, Scikit-learn (TF-IDF), FAISS, Google Gemini (Optional for feedback).
* **Data:** Kaggle Interview Question Dataset.

---

## ⚙️ Quick Start Guide

### 1. Prerequisites & Data
Place your Kaggle dataset (`new_interview_questions.csv`) in `backend/data/`.

### 2. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Visit `http://localhost:5173` to start.

---

## 📡 API Documentation

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **POST** | `/api/parse-resume` | Extracts profile from PDF/DOCX |
| **GET** | `/api/questions/{id}` | Retrieves FAISS-ranked questions |
| **POST** | `/api/score` | Semantic & Acoustic answer evaluation |
| **GET** | `/api/report/{id}` | Full session analytics & breakdown |

---

