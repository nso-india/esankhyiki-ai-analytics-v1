# MoSPI AI Analytics — e-Sankhyiki Data Query Chatbot

A natural-language-to-SQL analytics system that lets users query Indian statistical datasets (MoSPI) through a conversational chat interface. Powered by a local LLM (Llama 3 70B via Ollama) for deterministic query generation and a Plotly Dash frontend.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM Backend | Ollama · `llama3:70b` |
| Web Framework | Plotly Dash · Dash Bootstrap Components |
| Database | PostgreSQL (connection pooling via `psycopg2`) |
| Language | Python 3 |

---

## Project Structure

```
.
├── app_34.py          # Core query pipeline (LLM + SQL + DB)
├── dash_08.py         # Dash UI (chat interface, callbacks)
├── metadata.json      # Indicator & filter schema for all products
├── prompts/           # Per-product SQL prompt templates
│   ├── <product>/
│   │   ├── aggregation.prompt
│   │   └── non_aggregation.prompt
│   └── common/
│       ├── aggregation.prompt
│       └── non_aggregation.prompt
└── performance.json   # Auto-generated query performance log
```

---

## Supported Datasets (Products)

| Key | Dataset |
|---|---|
| `gender` | Gender Statistics |
| `envstat` | Environment Statistics |
| `iip` | Index of Industrial Production |
| `cpi` | Consumer Price Index (auto-routed) |
| `cpi_grp` | CPI – Group level (pre-2018) |
| `cpi_itm` | CPI – Item level (pre-2018) |
| `cpi_24` | CPI – 2024 series |
| `cpialrl` | CPI – Agricultural/Rural/Labour |
| `tus` | Time Use Survey |
| `hces` | Household Consumer Expenditure |
| `esi` | Energy Statistics |
| `plfs` | Periodic Labour Force Survey |
| `asi` | Annual Survey of Industries |
| `nas` | National Accounts Statistics |
| `aishe` | All India Survey on Higher Education |
| `wpi` | Wholesale Price Index |
| `asuse` | ASI Unit-level |
| `nfhs` | National Family Health Survey |
| `rbi` | RBI Statistics |
| `nss77/78/79` | NSS Rounds |

CPI queries are **auto-routed** to the correct sub-product based on year and keywords in the user query.

---

## Query Pipeline (`app_34.py`)

```
User Query
    │
    ├─► CPI Routing (if product = "cpi")
    │       year < 2018 + group keyword → cpi_grp
    │       year < 2018                 → cpi_itm
    │       default                     → cpi_24
    │
    ├─► Indicator Detection (LLM)
    │       Semantic match against metadata.json indicator list
    │       Fuzzy fallback via difflib
    │
    ├─► Aggregation Detection (keyword rule)
    │       "average / total / sum / mean" → aggregation mode
    │
    ├─► Filter Extraction (LLM)
    │       Extracts column values from schema
    │       Geography & year fallback rules applied
    │       Returns relevant_data + modified_query
    │
    ├─► SQL Generation (LLM, streaming)
    │       Loads product-specific prompt template
    │       Fills template placeholders
    │       Generates SELECT query
    │
    ├─► WHERE Normalization (rule-based)
    │       Fuzzy-matches all filter values to schema
    │       Ensures indicator LIKE condition is present
    │       Removes invalid/unrecognized conditions
    │
    ├─► Query Execution (PostgreSQL, 60s timeout)
    │       Read-only guard (SELECT only)
    │       Connection pool per database
    │
    └─► Retry / Fallback
            Up to 3 LLM-driven SQL correction attempts
            Dynamic fallback query if all retries fail
```

---

## LLM Determinism Settings

All three LLM calls (indicator detection, filter extraction, SQL generation) use identical parameters to guarantee reproducible outputs for identical inputs:

```python
OLLAMA_TEMPERATURE = 0
OLLAMA_SEED        = 42
OLLAMA_TOP_P       = 1
OLLAMA_TOP_K       = 1
```

---

## Running the App

### Prerequisites

- Python 3.9+
- Ollama running locally with `llama3:70b` pulled
- PostgreSQL accessible at `103.48.43.11:5432`

### Install dependencies

```bash
pip install dash dash-bootstrap-components plotly pandas psycopg2-binary requests
```

### Start Ollama

```bash
ollama serve
ollama pull llama3:70b
```

### Run the Dash app

```bash
python dash_08.py
```


### CLI mode (for testing)

```bash
python app_34.py
# Prompts for product name and query interactively
```

---

## UI Features

- **Natural language chat** with session history
- **Editable SQL** — generated SQL is shown in a textarea; users can modify and re-run it
- **Show Schema** — modal showing all columns and their distinct values for the active indicator
- **Multi-session** — multiple chat sessions with titles derived from the first query
- **Error hints** — human-readable hints for common SQL errors (wrong column, syntax, timeout, wrong table)

---

## Adding a New Product

1. Add the product key → database name to `DATABASE_MAPPING` in `app_34.py`.
2. Add the product key → prompt folder name to `PROMPT_FOLDER_MAPPING`.
3. Create `prompts/<product>/aggregation.prompt` and `non_aggregation.prompt`.
4. Add the product's indicators and filter schema to `metadata.json`.
5. If the product has non-standard value columns, add an entry to `FALLBACK_VALUE_COLUMNS`.

---

## Performance Logging

Every query is appended to `performance.json` with:

- Timestamp, user query, product, indicator
- Relevant/non-relevant columns and matched values
- All generated SQL attempts (initial, retries, fallback)
- All errors encountered
- Final SQL used

---

## Security

- **Read-only guard**: Any query not starting with `SELECT` is rejected before execution.
- **Statement timeout**: All queries are capped at 60 seconds via `SET statement_timeout`.
- **Connection pooling**: Min 2, max 5 connections per database via `psycopg2.SimpleConnectionPool`.
