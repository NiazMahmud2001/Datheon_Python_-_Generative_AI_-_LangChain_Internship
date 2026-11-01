# Datheon Internship: Python + Generative AI & LangChain

Portfolio projects for the Datheon **Python + Generative AI & LangChain Internship** (4-week program). Each task lives in its own folder, with its own README, `.env.example` and entry point.

**Author:** Niaz Mahmud ([@NiazMahmud2001](https://github.com/NiazMahmud2001))

---

## Task overview

| # | Task | Folder | Status |
|---|---|---|---|
| 1 | Structured LLM Prompt Pipeline & JSON Extractor | [`Structured LLM Prompt Pipeline & JSON Extractor/`](./Structured%20LLM%20Prompt%20Pipeline%20%26%20JSON%20Extractor) | ✅ Complete |
| 2 | Document Q&A Assistant with RAG & Vector Embeddings | (not in this repository yet) | ⏳ Planned |
| 3 | Multi-Tool Autonomous AI Agent | [`Multi-Tool Autonomous AI Agent/`](./Multi-Tool%20Autonomous%20AI%20Agent) | ✅ Complete |
| 4 | Interactive Full-Stack AI Chatbot with Streamlit | (not in this repository yet) | ⏳ Planned |

---

## Repository structure

```
.
├── README.md                                        ← you are here
│
├── Structured LLM Prompt Pipeline & JSON Extractor/ ← Task 1
│   ├── README.md          # detailed documentation
│   ├── main.py            # entry point: Pydantic schema + LangGraph pipeline
│   ├── prompt.py          # parameterized prompt templates
│   ├── some_demo_invoices/  # 6 input PDF invoices (different layouts)
│   ├── output/            # validated JSON results (already generated)
│   └── .env.example
│
└── Multi-Tool Autonomous AI Agent/                  ← Task 3
    ├── README.md          # detailed documentation
    ├── main.py            # entry point: Gradio chat UI
    ├── main_for_graph.py  # LangGraph agent + run_agent()
    ├── tools.py           # web search, calculator, file reader
    ├── file_storage/      # sandbox folder for read_file (sample: sales_q3.txt)
    └── .env.example
```

---

## Quick start (for reviewers)

### Prerequisites

- **Python 3.11 – 3.13** recommended. Python 3.14 works, but LangChain prints a harmless Pydantic V1 compatibility warning.
- An **OpenRouter API key** (free): https://openrouter.ai/keys. Used by both tasks.
- A **Tavily API key** (free tier): https://tavily.com. Used by Task 3 only.

Both tasks use free OpenRouter models, so they cost nothing to run.

### Task 1: Structured JSON Extractor

```bash
cd "Structured LLM Prompt Pipeline & JSON Extractor"
pip install langgraph pydantic pymupdf openrouter python-dotenv
cp .env.example .env          # Windows: copy .env.example .env
# open .env and set OPENROUTER_API_KEY
python main.py
```

**Expected result:** every PDF in `some_demo_invoices/` is extracted, validated and saved to `output/<invoice name>.json`, plus a combined `output/all_invoices.json`.

> **No API key?** The results from a real run are already committed in [`output/`](./Structured%20LLM%20Prompt%20Pipeline%20%26%20JSON%20Extractor/output), so you can check them without running anything.

### Task 3: Multi-Tool Autonomous AI Agent

```bash
cd "Multi-Tool Autonomous AI Agent"
pip install langgraph langchain-openai langchain-core langchain-community langchain-tavily gradio pydantic python-dotenv
cp .env.example .env          # Windows: copy .env.example .env
# open .env and set OPENROUTER_API_KEY and TAVILY_API_KEY
python main.py
```

**Expected result:** a Gradio chat UI opens at http://127.0.0.1:7860. Ask a multi-step question, for example:

> *What is the current population of Bangladesh? Divide it by 64 districts.* (web search → calculator)
>
> *Read sales_q3.txt and calculate the total Q3 revenue.* (file reader → calculator)

The reply shows the full reasoning chain: `Thought → Action → Observation → … → Final Answer`.

To try the agent without the UI:

```bash
python main_for_graph.py
```

---

## Requirement checklist

### Task 1: Structured LLM Prompt Pipeline & JSON Extractor

| Requirement | Implementation | Where |
|---|---|---|
| Connect Python to an LLM API | OpenRouter Python SDK (OpenAI-compatible API) with `temperature=0` and a timeout | `main.py` → `LLM_Call()` |
| Parameterized prompt templates | `SYSTEM_PROMPT(schema, example)`, `USER_PROMPT(file_name, invoice_text)`, `RETRY_PROMPT(previous_output, errors)` | `prompt.py` |
| Few-shot examples | A worked input → output example inside the system prompt | `prompt.py` → `EXAMPLE_OUTPUT` |
| Strictly validated JSON | Pydantic v2 models with `extra="forbid"`, typed dates, a currency regex and value bounds | `main.py` → `Invice_Infos`, `Each_Line_Items`, `Invoice_Issue_Receive`, `PaymentInfo` |
| Business-rule validation | `qty × unit_price = amount`, `Σ items = subtotal`, `subtotal + tax = total` | `main.py` → `check_amount()`, `check_totals()` |
| Enforce the format with a loop | LangGraph loop: on a validation error, the errors go back to the LLM and it retries, up to `MAX_RETRIES`, then the invoice is skipped | `main.py` → `LLM_Call_Node`, `condition_2_error_loop`, `skip_invoice_Node` |
| **Deliverable:** executable script that parses unstructured documents into validated JSON | `python main.py` processes 6 differently laid-out PDF invoices | `main.py`, `output/` |

### Task 3: Multi-Tool Autonomous AI Agent

| Requirement | Implementation | Where |
|---|---|---|
| LangChain / function-calling agent | LangChain `@tool`s bound to the LLM with `bind_tools()`, run in a LangGraph agent loop | `main_for_graph.py` |
| Real-time web search | Tavily search (`langchain-tavily`). The task allows DuckDuckGo *or* Tavily | `tools.py` → `tool_search_int` |
| Python math calculator | AST-based safe evaluator (no `eval()`): numbers and `+ - * / ** %` only | `tools.py` → `calculator` |
| Local file reader | Reads a text file by name, sandboxed to `file_storage/` (`../` path traversal is blocked, so `.env` cannot be read) | `tools.py` → `read_file` |
| Agent executor loop | `agent → tools → agent …` until no more tool calls, with a `MAX_TOOL_CALLS` guard and a forced final answer | `main_for_graph.py` → `agent_call_node`, `route_after_calling_agent`, `tool_limit_node` |
| Show the reasoning chain | Streams each node's output and labels it **Thought / Action / Observation / Final Answer** | `main_for_graph.py` → `run_agent()` |
| Extras | Per-session conversation memory (`InMemorySaver` + `thread_id`), typed Pydantic state, Gradio chat UI | `main_for_graph.py`, `main.py` |

---

## Environment variables

Each task has its own `.env.example`. Copy it to `.env` in the **same folder** before running.

| Variable | Task | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | 1, 3 | OpenRouter API key |
| `MAX_RETRIES` | 1 | Validation retries per invoice before it is skipped (default `3`) |
| `LLM_MAX_TOKENS` | 1 | Max tokens in an LLM response |
| `LLM_TIMEOUT_SECONDS` | 1 | Timeout for one LLM call |
| `TAVILY_API_KEY` | 3 | Tavily web search API key |
| `MAX_TOOL_CALLS` | 3 | Max tool calls per question before the agent is forced to answer (default `5`) |

Real `.env` files are git-ignored. API keys are never committed.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `401 User not found` / `Unauthorized` | The OpenRouter key is missing or invalid. Check `.env` in the task folder. |
| `TypeError: int() argument ... 'NoneType'` | A numeric variable from `.env.example` is missing in `.env`. |
| Free model is slow, times out or returns empty | Free OpenRouter models are rate-limited. Re-run, or change the model name in `LLM_Call()` (Task 1) or in `ChatOpenAI(model=...)` (Task 3). Task 3 needs a model that supports **tool calling**. |
| `UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14` | Harmless warning from LangChain. Use Python 3.11–3.13 to hide it. |

---

## Tech stack

Python · LangChain · LangGraph · Pydantic v2 · OpenRouter · Tavily · PyMuPDF · Gradio
