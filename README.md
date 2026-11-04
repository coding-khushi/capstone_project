# Percept — A Context-Aware Desktop AI Assistant

**Percept looks at your screen first, fetches only what's missing, and asks before it reads.**

Percept is a floating desktop assistant. You start a screen session, ask a question in plain language, and Percept answers from what is on your screen. When the screen is not enough (for example, the function you are asking about is defined in another file), a Context Manager decides what is missing and retrieves only that piece of project context — never the whole project, and never a file without your permission.

---

## Features

- **Floating panel** — always-on-top window, opened with `Ctrl+Shift+P` (Windows) / `Cmd+Shift+P` (macOS) or from the tray.
- **Screen understanding** — while recording is on, one frame is captured each time you send a question and read by a multimodal model (Gemini).
- **Context Manager agent** — decides whether the screen is enough; if not, calls retrieval tools (at most 4 rounds per question).
- **Code retrieval** — find where a symbol is defined, where it is used, or search the project by meaning, using a Tree-sitter + SQLite index.
- **Document reading** — reads `.pptx`, `.pdf`, `.docx`, `.zip` and text files you grant access to, even while they are open in PowerPoint/Word.
- **Permission-gated file access** — *Grant Access* banner and *Allow / Deny* modal; permissions are one-time and can be revoked.
- **Active file detection** — knows which file is open in VS Code (Windows and macOS).
- **Markdown + LaTeX answers** — rendered with react-markdown and KaTeX.

## How it works

```
┌─────────────────────┐   POST /api/v1/query    ┌──────────────────────────┐
│  Desktop app        │ ──────────────────────► │  Backend (FastAPI)       │
│  Electron + React   │  question + screenshot  │  Gemini agent loop       │
│                     │ ◄────────────────────── │  (Context Manager)       │
└─────────────────────┘   answer + sources      └──────────┬───────────────┘
                                                           │ tools (only when needed)
                                             ┌─────────────┴─────────────┐
                                             │ find_definition           │──► SQLite index
                                             │ find_references           │    (Tree-sitter symbols
                                             │ search_project            │     + embeddings)
                                             │ suggest_file_access       │
                                             │ get_file (needs permission)──► your files
                                             └───────────────────────────┘
```

1. You press **record (●)** and ask a question; the app captures one frame of the screen.
2. The backend sends the frame and question to Gemini with the Context Manager's rules.
3. If the screen answers it, Gemini replies directly.
4. If not, Gemini calls a tool (e.g. `find_definition`), reads the result and continues — up to 4 rounds.
5. Reading a file requires your permission; the answer names the file it used.

## Repository structure

```
capstone_project/
├── desktop/                     Electron + React desktop app
│   ├── electron/main.ts         window, tray, global shortcut, screen capture
│   ├── electron/preload.ts      safe bridge between the UI and Electron
│   └── renderer/src/            React UI (ChatPanel, PermissionModal, ProjectPanel, ...)
├── backend/                     Python FastAPI backend
│   ├── main.py                  starts the server on port 8000
│   ├── api/routes.py            /query, /index, /project/structure
│   ├── ai/context_manager.py    system prompt, tool declarations, agent loop
│   ├── retrieval/tools.py       retrieval tools, document readers, active-file detection
│   ├── indexing/                Tree-sitter indexer and sentence-transformer embeddings
│   ├── database/models.py       SQLite models (projects, files, symbols, embeddings)
│   ├── screen/processor.py      screenshot validation
│   └── debug_logger.py          optional interaction log (off by default)
├── evaluation/                  screen-only vs screen-plus-retrieval benchmark
└── docker/                      Docker setup for the backend
```

## Getting started

### Prerequisites

- **Python 3.13** (3.11+ should work)
- **Node.js 18+** and npm
- A **Google AI Studio API key** for Gemini — https://aistudio.google.com/apikey

### 1. Backend

**Windows**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # then put your GOOGLE_API_KEY in .env
python main.py
```

**macOS**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then put your GOOGLE_API_KEY in .env
python main.py
```

The server runs at `http://localhost:8000` (API docs at `http://localhost:8000/docs`).

### 2. Desktop app

In a second terminal:
```bash
cd desktop
npm install
npm run dev
```

The Percept panel appears at the bottom-right of the screen. On macOS, allow **Screen Recording** permission for the terminal/Electron when asked (System Settings → Privacy & Security), and **Accessibility** permission for active-file detection.

### 3. Index a project (optional, for code questions)

Click the folder icon in the Percept header → choose your project folder → **Index**. Percept parses Python, JavaScript and TypeScript files and reports the files, symbols and embeddings it created.

## Using Percept

| You want to… | Do this |
|---|---|
| Ask about your screen | Press **●** to start recording, then ask (e.g. *"What error is this?"*) |
| Ask a general question | Just ask — no recording needed |
| Let Percept read a document on screen | Click **Grant Access** on the banner and pick the file |
| Ask about code in other files | Index the project, then ask (e.g. *"Where is this function defined?"*) |
| Start fresh | **New Chat** clears messages and all granted files |
| Revoke a file | Click **✕** on its chip under the header |

## Configuration

`backend/.env`:

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | — (required) | Gemini API key |
| `PERCEPT_DEBUG_LOG` | `0` | Set to `1` to save questions, answers and screenshots to `backend/debug_sessions/` for debugging. Off by default for privacy. |

The Gemini model is set by `GEMINI_MODEL` in `backend/ai/context_manager.py` (default `gemini-3.5-flash-lite`).

## Privacy

- Nothing is captured until you press record; a visible indicator stays on while it runs.
- Only **one frame per question** is sent to the model — there is no continuous upload.
- Percept's own window is **excluded from screen capture**, so it never reads its own chat.
- **No file is read without permission**; permissions are one-time, revocable and never stored.
- Screenshots and chats are **not saved to disk** unless `PERCEPT_DEBUG_LOG=1`.
- The API key stays in a local `.env` file excluded from git.

Captured frames are processed by a cloud model (Gemini), so anything visible on screen when you send a question leaves the device.

## Evaluation

The benchmark compares **screen-only** answers with **screen + retrieval** answers on 9 questions built from this codebase (4 answerable from the screen, 5 that need code from another file). Each question is answered twice by the same agent.

```bash
# from the repo root, with the backend venv (server does not need to be running)
backend/venv/Scripts/python.exe evaluation/evaluate.py          # Windows
backend/venv/bin/python evaluation/evaluate.py                  # macOS
backend/venv/Scripts/python.exe evaluation/evaluate.py RT-01    # re-run selected cases
```

Results (`evaluation/results_summary.md`):

| Question type | Mode | Accuracy | Correct retrieval decision | Right file found | Context tokens |
|---|---|---|---|---|---|
| Answerable from screen | Screen only | 100% | – | – | ~2,000 |
| Answerable from screen | Screen + retrieval | 100% | 100% | – | ~2,800 |
| Needs another file | Screen only | 0% | – | – | ~2,000 |
| Needs another file | Screen + retrieval | **100%** | **100%** | **100%** | ~8,200 |

Retrieval raised accuracy from 0% to 100% on questions whose answer lives in another file, the agent made no unnecessary tool calls on screen-answerable questions, and screen-only mode said when an answer was not visible instead of guessing. `evaluation/make_screens.py` regenerates the benchmark screenshots.

## Platform support

| | Windows | macOS |
|---|---|---|
| Desktop app & screen capture | ✅ | ✅ |
| Capture exclusion of Percept's window | ✅ (Windows 10 2004+) | ✅ |
| Active VS Code file detection | ✅ (Win32 API) | ⚠️ AppleScript; only when VS Code is the front app, not re-tested |
| Reading documents open in Office apps | ✅ | ✅ |

## Known limitations

- Response time depends on Gemini API load (roughly 2–21 s per question); "503 high demand" errors are on Google's side — wait and retry.
- The free Gemini tier allows a limited number of requests per day; each tool round counts as a request.
- Semantic search embeds symbol names, not full code bodies; exact lookups (`find_definition`, `find_references`) are the most reliable tools.
- Qdrant is listed in `docker/` but not used — embeddings are stored in SQLite, which is enough for project-sized indexes.
- No separate OCR stage — Gemini reads the screenshot directly.

## Tech stack

Electron · React · TypeScript · Vite · Python · FastAPI · Google Gemini (`google-genai`) · Tree-sitter · SQLite / SQLAlchemy · sentence-transformers · python-pptx · pypdf · python-docx · KaTeX

## Team

| Member | Role |
|---|---|
| **Khushi** | AI & screen understanding, Context Manager flow, macOS development |
| **Navneet** | Backend & project retrieval, Windows support & compatibility, Windows build & testing |
| **Aakhil** | Testing & evaluation, macOS testing, benchmark & documentation |

Capstone Project, 2026.
