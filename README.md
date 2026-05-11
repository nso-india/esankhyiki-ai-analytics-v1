# e-Sankhyiki AI Analytics
**License: MIT &nbsp;|&nbsp; Python 3.9+ &nbsp;|&nbsp; Powered by Ollama + Llama 3 &nbsp;|&nbsp; Built with Plotly Dash**

Natural-language-to-SQL analytics system for India's Ministry of Statistics and Programme Implementation (MoSPI) datasets. Users ask questions in plain English; the system detects the statistical indicator, extracts filters, generates and validates SQL, executes it against PostgreSQL, and returns results — all automatically through a chat interface.

---

## Table of Contents

1. [Overview](#overview)
2. [Datasets](#datasets)
3. [Query Pipeline](#query-pipeline)
4. [Quick Start](#quick-start)
5. [Installation](#installation)
6. [Running the App](#running-the-app)
7. [Accessing the UI](#accessing-the-ui)
8. [Using the Chat Interface](#using-the-chat-interface)
9. [Project Structure](#project-structure)
10. [Configuration](#configuration)
11. [metadata.json — Schema File](#metadatajson--schema-file)
12. [Prompt Templates](#prompt-templates)
13. [CPI Auto-Routing](#cpi-auto-routing)
14. [Adding a New Dataset](#adding-a-new-dataset)
15. [LLM Determinism](#llm-determinism)
16. [Database Details](#database-details)
17. [Fallback & Retry Logic](#fallback--retry-logic)
18. [Performance Logging](#performance-logging)
19. [Security](#security)
20. [Troubleshooting](#troubleshooting)

---

## Overview

This system provides a conversational interface over official Indian government statistical databases. It bridges plain-English questions with PostgreSQL query execution, using a locally-running Llama 3 model (via Ollama) for all language understanding tasks.

**Key Features:**

- 22 statistical datasets covering employment, inflation, industrial production, GDP, energy, higher education, gender, health, environment, trade, agriculture, and consumption
- 8-stage deterministic pipeline: routing → indicator detection → filter extraction → SQL generation → normalization → execution → retry → fallback
- Editable SQL with live re-execution in the UI
- Schema viewer showing available columns and distinct values per indicator
- Multi-session chat history
- Production-safe: read-only guard, 60-second query timeout, connection pooling
- Fully local — no external API calls; all LLM inference runs on your machine via Ollama

---

## Datasets

| Key | Full Name | Use For |
|---|---|---|
| `gender` | Gender Statistics | Sex ratio, literacy by gender, women empowerment |
| `envstat` | Environment Statistics | Climate, pollution, biodiversity, forests, water |
| `iip` | Index of Industrial Production | Industrial growth, manufacturing output |
| `cpialrl` | CPI for Agricultural/Rural Labourers | Rural inflation, agricultural labourer cost of living |
| `cpi` | Consumer Price Index (auto-routed) | Retail inflation — routes to sub-product automatically |
| `cpi_grp` | CPI – Group level (pre-2018) | Group-level CPI before 2018 series |
| `cpi_itm` | CPI – Item level (pre-2018) | Item-level CPI before 2018 series |
| `cpi_24` | CPI – 2024 series | Current CPI series from 2018 onwards |
| `tus` | Time Use Survey | Time allocation, unpaid work, gender time gaps |
| `hces` | Household Consumption Expenditure Survey | Consumer spending, poverty, inequality (Gini) |
| `esi` | Energy Statistics | Energy production, consumption, fuel mix |
| `plfs` | Periodic Labour Force Survey | Jobs, unemployment, wages, workforce participation |
| `asi` | Annual Survey of Industries | Factory performance, industrial employment |
| `nas` | National Accounts Statistics | GDP, economic growth, national income |
| `aishe` | All India Survey on Higher Education | Universities, colleges, enrolment, GER, GPI |
| `wpi` | Wholesale Price Index | Wholesale inflation, producer prices |
| `asuse` | Annual Survey of Unincorporated Enterprises | Informal sector, small businesses, MSME |
| `nfhs` | National Family Health Survey | Fertility, infant mortality, maternal care, nutrition |
| `rbi` | RBI Statistics | Forex, exchange rates, trade, balance of payments |
| `nss77` | NSS 77th Round | Land, livestock, farm income, crop insurance |
| `nss78` | NSS 78th Round | Drinking water, sanitation, digital connectivity |
| `nss79` | NSS 79th Round | Literacy, health expenditure, financial inclusion |

---

## Query Pipeline

The system runs 8 sequential steps on every user query:

```
User Query  (e.g. "CPI inflation in Bihar in 2022")
     │
     ▼
[1] CPI ROUTING  — only when product = "cpi"
     │   Analyses year and keywords → picks cpi_grp / cpi_itm / cpi_24
     │
     ▼
[2] INDICATOR DETECTION  — LLM call #1
     │   Reads indicator list from metadata.json
     │   LLM semantically matches query → indicator name
     │   Fuzzy fallback via difflib if LLM output is slightly off
     │
     ▼
[3] AGGREGATION DETECTION  — rule-based, no LLM
     │   Keywords: average / total / sum / mean
     │   Selects aggregation.prompt or non_aggregation.prompt
     │
     ▼
[4] FILTER EXTRACTION  — LLM call #2
     │   Schema (columns + distinct values) sent to LLM
     │   LLM returns matched values + rewritten modified_query
     │   Geography fallback: city → state → All India
     │   Year fallback: unrecognised year → nearest schema year
     │
     ▼
[5] SQL GENERATION  — LLM call #3, streaming
     │   Loads prompts/<product>/[aggregation|non_aggregation].prompt
     │   Fills $placeholders and sends to LLM
     │   LLM returns a raw SELECT query
     │
     ▼
[6] WHERE NORMALIZATION  — rule-based, no LLM
     │   Parses each WHERE condition individually
     │   Fuzzy-matches every value against the schema (cutoff 0.6)
     │   Ensures indicator LIKE '%token1%token2%' is always present
     │   Removes malformed or unrecognised conditions
     │   Enforces LIMIT (default 500 rows)
     │
     ▼
[7] QUERY EXECUTION  — PostgreSQL
     │   Read-only guard: rejects anything not starting with SELECT
     │   60-second statement_timeout per query
     │   Connection pool: min 2, max 5 connections per database
     │
     ▼
[8] RETRY / FALLBACK  — triggered only on DB error
         Up to 3 LLM-driven SQL correction attempts
         Each retry runs through WHERE normalization again
         If all 3 fail → dynamic fallback query (LIMIT 100)

Result rows → rendered as HTML table in Dash UI
```

---

## Quick Start

### Prerequisites at a glance

- Python 3.9+
- [Ollama](https://ollama.com/download) with `llama3:70b` pulled (~40 GB download)
- PostgreSQL server accessible on your network

```bash
# 1. Pull the LLM model (do this once)
ollama pull llama3:70b

# 2. Clone and install
git clone <your-repo-url>
cd <repo-folder>
pip install -r requirements.txt

# 3. Start Ollama
ollama serve

# 4. Run the app
python dash_08.py
```

Open: `http://localhost:5020/sql-search/<product_key>`
Example: `http://localhost:5020/sql-search/gender`

---

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd <repo-folder>

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# Install all dependencies
pip install dash dash-bootstrap-components plotly pandas psycopg2-binary requests
```

> **Hardware note:** `llama3:70b` requires at least **48 GB RAM** or equivalent GPU VRAM.
> For lower-spec machines, change `OLLAMA_MODEL = "llama3:8b"` in `app_34.py` — lighter but less accurate.

---

## Running the App

### Step 1 — Start Ollama

```bash
ollama serve
```

Verify it is running:

```bash
curl http://localhost:11434/api/tags
```

### Step 2 — Start the Dash app

```bash
python dash_08.py
```

Expected output:

```
Dash is running on http://0.0.0.0:5020/sql-search/
```

### CLI Mode — test without UI

Runs the full pipeline interactively in the terminal; useful for debugging:

```bash
python app_34.py
```

```
Enter product name: gender
Enter your query: What is the sex ratio in Bihar in 2021?
```

Every pipeline stage is printed — indicator detected, filters extracted, SQL generated, WHERE normalised, DB result rows.

---

## Accessing the UI

The product name is always part of the URL path:

```
http://localhost:5020/sql-search/<product_key>
```

| URL | Opens |
|---|---|
| `http://localhost:5020/sql-search/gender` | Gender Statistics |
| `http://localhost:5020/sql-search/cpi` | CPI (auto-routed to sub-product) |
| `http://localhost:5020/sql-search/plfs` | Periodic Labour Force Survey |
| `http://localhost:5020/sql-search/nfhs` | National Family Health Survey |
| `http://localhost:5020/sql-search/nas` | National Accounts Statistics |

> If you open `/sql-search/` without a product key, a modal will prompt you to enter the full URL manually.

---

## Using the Chat Interface

### Asking a question

Type any plain-English question and press **Enter** or click the send button.

```
What is the literacy rate in Rajasthan in 2021?
Show total CPI inflation for all states in 2023
Average sex ratio in rural areas from 2015 to 2020
Top 5 states by energy consumption in 2022
Monthly CPI for Bihar January 2023
```

### Editing and re-running SQL

Every successful response shows the **Generated SQL** in an editable text box above the results table.

- Modify the SQL directly — change filters, add columns, adjust LIMIT, etc.
- Click **▶ Run Query** — the result table updates immediately
- The system automatically enforces `LIMIT 100` on manual re-runs

### Show Schema

Click **⊞ Show Schema** on any response to open a modal listing all columns and their distinct valid values for the detected indicator. Use this to understand exactly what filter values are available before refining a query.

### Chat History

- All sessions appear in the left sidebar, titled from the first query
- Click any session to restore it
- Click **+ New Chat** to start fresh
- Sessions persist in memory for the duration of the app session (not saved to disk)

---

## Project Structure

```
project-root/
│
├── app_34.py               # Core pipeline — LLM calls, SQL generation, DB execution
├── dash_08.py              # Dash web UI — layout, callbacks, chat sessions
│
├── metadata.json           # REQUIRED — indicator & filter schema for every product
│
├── prompts/                # REQUIRED — SQL generation prompt templates
│   ├── common/
│   │   ├── aggregation.prompt
│   │   └── non_aggregation.prompt
│   ├── gender/
│   │   ├── aggregation.prompt
│   │   └── non_aggregation.prompt
│   ├── cpi_grp/
│   ├── cpi_itm/
│   ├── cpi_24/
│   ├── cpialrl/
│   ├── envstat/
│   ├── iip/
│   ├── tus/
│   ├── hces/
│   ├── esi/
│   ├── plfs/
│   ├── asi/
│   ├── nas/
│   ├── aishe/
│   ├── wpi/
│   ├── asuse/
│   ├── nfhs/
│   ├── rbi/
│   ├── nss77/
│   ├── nss78/
│   └── nss79/
│
└── performance.json        # AUTO-GENERATED — query log (do not edit manually)
```

**Design principles:**

| Principle | Implementation |
|---|---|
| metadata as source of truth | All valid indicator names and filter values come from `metadata.json`; LLM never invents values |
| Determinism first | Fixed `seed=42`, `temperature=0`, `top_p=1`, `top_k=1` on every LLM call |
| Normalize always | WHERE clause is rule-based fuzzy-matched against schema after every LLM generation |
| Defence in depth | Read-only SQL guard → retry × 3 → dynamic fallback query |
| LLM-optimized prompts | Per-product prompt templates with placeholders tuned to each dataset's schema |

---

## Configuration

All configuration is at the top of `app_34.py`.

### LLM settings

```python
OLLAMA_BASE_URL    = "http://localhost:11434"   # Ollama server URL
OLLAMA_MODEL       = "llama3:70b"               # Model to use
OLLAMA_TIMEOUT     = 120                        # Seconds per LLM call
OLLAMA_TEMPERATURE = 0                          # 0 = fully deterministic
OLLAMA_SEED        = 42                         # Fixed seed for reproducibility
OLLAMA_TOP_P       = 1                          # Disable nucleus sampling
OLLAMA_TOP_K       = 1                          # Always pick top-1 token
```

### Database credentials

Find `get_db_pool()` in `app_34.py` and update:

```python
db_pools[db_name] = SimpleConnectionPool(
    2, 5,
    port     = 5432,
    user     = "postgres",       # ← your DB username
    database = db_name
)
```

### Database mapping

Maps each product key to its PostgreSQL database name. Update `DATABASE_MAPPING` if your names differ:

```python
DATABASE_MAPPING = {
    "gender":  "gender_db",
    "cpi_grp": "cpi2_db",
    # ... etc.
}
```

### App port

At the bottom of `dash_08.py`:

```python
app.run(debug=False, port=5020)   # change port here
```

---

## metadata.json — Schema File

This is the most critical file. It defines every indicator available per product and every valid filter value per indicator. The LLM uses it as its sole source of truth when extracting filters and matching values — it will never invent a value not present here.

### Structure

```json
{
  "datasets": {
    "<product_key>": {
      "indicators": [
        {
          "indicator_name": "Exact Indicator Name As In DB",
          "filters": [
            { "year":   ["2019", "2020", "2021", "2022"] },
            { "state":  ["All India", "Bihar", "Gujarat", "Maharashtra"] },
            { "sector": ["Rural", "Urban", "Total"] }
          ]
        },
        {
          "indicator_name": "Another Indicator",
          "filters": [
            { "financial_year": ["2019-20", "2020-21", "2021-22"] },
            { "state":  ["All India", "Bihar", "Gujarat"] },
            { "gender": ["Male", "Female", "Total"] }
          ]
        }
      ]
    }
  }
}
```

### Rules

| Rule | Detail |
|---|---|
| `indicator_name` | Must exactly match the `indicator` column value in your `data_view` table — case-sensitive |
| Filter keys | Must exactly match database column names — case-sensitive |
| Filter values | Must exactly match distinct values stored in the database |
| Year columns | Any key containing `"year"` (e.g. `year`, `financial_year`, `base_year`) is automatically treated as a year column |
| Value format | All values must be strings — use `"2022"` not `2022` |

### How to generate it from your database

```sql
-- Step 1: Get all distinct indicators for a product
SELECT DISTINCT indicator FROM data_view ORDER BY indicator;

-- Step 2: For each indicator, get distinct values per column
SELECT DISTINCT year   FROM data_view WHERE indicator = 'Sex Ratio' ORDER BY year;
SELECT DISTINCT state  FROM data_view WHERE indicator = 'Sex Ratio' ORDER BY state;
SELECT DISTINCT sector FROM data_view WHERE indicator = 'Sex Ratio' ORDER BY sector;
```

Build the JSON from these results. Repeat for every indicator in every product database.

---

## Prompt Templates

Each product has two prompt files under `prompts/<product>/`:

| File | Used when |
|---|---|
| `non_aggregation.prompt` | Query has no aggregation keywords |
| `aggregation.prompt` | Query contains: `average` / `total` / `sum` / `mean` |

If no product folder exists, the system falls back to `prompts/common/`.

### Available placeholders

These are substituted automatically before the prompt is sent to the LLM:

| Placeholder | Replaced with |
|---|---|
| `$modified_query` | User query rewritten with schema-matched values |
| `$indicator` | Detected indicator name |
| `$relevant_columns` | JSON list of relevant column names |
| `$non_relevant_columns` | JSON list of columns not referenced in the query |
| `$matched_values` | JSON dict: `{ "column": ["value1", "value2"] }` |
| `$select_columns` | JSON list of all columns to SELECT |
| `$where_conditions` | Pre-built `col IN ('v1','v2')` lines for the WHERE clause |

### Minimal example prompt

```
You are a PostgreSQL expert. Generate a SELECT query.

User query: $modified_query
Indicator: $indicator
Matched values: $matched_values
Non-relevant columns (SELECT but not WHERE): $non_relevant_columns

Rules:
- Table name is always: data_view
- Always filter indicator using LIKE
- Use WHERE conditions: $where_conditions
- Include all columns: $select_columns

Output ONLY the SQL. No markdown. No backticks. Start with SELECT. End with semicolon.
```

---

## CPI Auto-Routing

When the product in the URL is `cpi`, the system automatically selects the correct sub-product before any other step runs, by analysing the user query:

| Condition | Routes to |
|---|---|
| Query mentions `group` / `grp` / `groups` AND a year before 2018 | `cpi_grp` |
| Query mentions a year before 2018 (no group keyword) | `cpi_itm` |
| All other queries | `cpi_24` (default) |

**Examples:**

```
"CPI group index in 2015"        → cpi_grp
"CPI inflation in Bihar in 2016" → cpi_itm
"CPI in Maharashtra in 2023"     → cpi_24
"What was inflation last month?"  → cpi_24
```

---

## Adding a New Dataset

Follow all 5 steps. Skipping any one will cause the product to fail silently.

### Step 1 — Add to `DATABASE_MAPPING` in `app_34.py`

```python
DATABASE_MAPPING = {
    # existing entries ...
    "myproduct": "myproduct_db",   # product key → PostgreSQL database name
}
```

### Step 2 — Add to `PROMPT_FOLDER_MAPPING` in `app_34.py`

```python
PROMPT_FOLDER_MAPPING = {
    # existing entries ...
    "myproduct": "myproduct",      # product key → prompts subfolder name
}
```

### Step 3 — Add to `FALLBACK_VALUE_COLUMNS` if value column is not `indicator_value`

```python
FALLBACK_VALUE_COLUMNS = {
    # existing entries ...
    "myproduct": "value_col1, value_col2",
}
```

Skip this step if your table uses `indicator_value` as the value column (the default).

### Step 4 — Create prompt templates

```
prompts/
└── myproduct/
    ├── non_aggregation.prompt
    └── aggregation.prompt
```

Write SQL generation instructions using the placeholders from the [Prompt Templates](#prompt-templates) section.

### Step 5 — Add indicators and filters to `metadata.json`

```json
{
  "datasets": {
    "myproduct": {
      "indicators": [
        {
          "indicator_name": "My First Indicator",
          "filters": [
            { "year":  ["2020", "2021", "2022"] },
            { "state": ["All India", "Bihar", "Gujarat"] }
          ]
        }
      ]
    }
  }
}
```

Access the new product at: `http://localhost:5020/sql-search/myproduct`

---

## LLM Determinism

All three LLM calls use a fixed parameter set so that the same question always produces the same SQL:

```python
OLLAMA_TEMPERATURE = 0    # No randomness in token selection
OLLAMA_SEED        = 42   # Fixed random seed (honoured by Ollama)
OLLAMA_TOP_P       = 1    # Disable nucleus sampling
OLLAMA_TOP_K       = 1    # Always pick the top-1 token
```

This guarantees production consistency: running the same query on different days yields identical results. To test prompt variability, temporarily set `OLLAMA_TEMPERATURE = 0.2` and run the same query several times.

---

## Database Details

### Table / view name per product

| Product | Table / View queried |
|---|---|
| `cpi_grp` | `data_view_grp` |
| `cpi_itm` | `data_view_itm` |
| `cpi_24` | `data_view_24` |
| All other products | `data_view` |

### Minimum required columns

| Column | Purpose |
|---|---|
| `indicator` | Text; must match indicator names in `metadata.json` exactly |
| Filter columns | All columns listed as keys in the indicator's `filters` array |
| Value column | `indicator_value` by default; override per product in `FALLBACK_VALUE_COLUMNS` |

### Connection pool

- Min 2, max 5 connections per database (configurable in `get_db_pool()`)
- Pools are created lazily on first query and reused for all subsequent requests
- Statement timeout: 60 seconds per query (configurable in `execute_query()`)

---

## Fallback & Retry Logic

### SQL retry — up to 3 attempts

When the first SQL execution fails with a database error:

1. The error message and original context are sent back to the LLM
2. The LLM generates a corrected query
3. WHERE normalization and LIMIT enforcement run again on the corrected query
4. The query is re-executed
5. This repeats up to 3 times

### Dynamic fallback query — when all retries fail

If all 3 correction attempts fail, the system programmatically builds a safe fallback query — no LLM involved:

```sql
SELECT <all_filter_columns>, <value_columns>
FROM data_view
WHERE indicator LIKE '%first_token%second_token%'
ORDER BY <first_year_column>
LIMIT 100;
```

This guarantees that some data is always returned for the detected indicator, even if the user-specified filters could not be resolved.

---

## Performance Logging

Every query — successful or failed — is automatically appended to `performance.json` in the project root.

### Log entry structure

```json
{
  "timestamp":                "2024-06-15 14:32:10",
  "user_query":               "Sex ratio in Bihar 2021",
  "product":                  "gender",
  "indicator":                "Sex Ratio",
  "aggregation":              "no",
  "prompt_folder_used":       "gender",
  "prompt_file_used":         "non_aggregation.prompt",
  "relevant_columns":         ["year", "state"],
  "distinct_relevant_values": { "year": ["2021"], "state": ["Bihar"] },
  "non_relevant_columns":     ["sector", "gender"],
  "all_generated_sql": [
    { "type": "initial",         "sql": "SELECT ..." },
    { "type": "retry_attempt_1", "sql": "SELECT ..." }
  ],
  "all_errors": [
    { "type": "initial", "error": "column xyz does not exist" }
  ],
  "final_sql_used": "SELECT ...",
  "final_error": null
}
```

### How to use the log

| Field to check | What it tells you |
|---|---|
| `indicator` | Was the right indicator detected? If wrong, improve indicator names in `metadata.json` |
| `distinct_relevant_values` | Did the LLM extract correct filter values? If wrong, improve the filter extraction prompt |
| `all_errors` | What DB errors occurred? Use to identify schema mismatches |
| `all_generated_sql` | How many retries were needed? If always >1, improve the SQL generation prompt |
| `final_error` not null | The fallback query was used; investigate why SQL generation keeps failing |

---

## Security

| Protection | Implementation |
|---|---|
| **Read-only guard** | Every SQL string is checked with a regex before execution; anything not starting with `SELECT` is rejected — no `INSERT`, `UPDATE`, `DELETE`, or `DROP` can ever run |
| **Statement timeout** | `SET statement_timeout = 60000` runs before every query; long-running queries are automatically cancelled |
| **Connection pooling** | Max 5 connections per database prevents connection exhaustion under concurrent load |
| **Fixed product routing** | The database name is resolved from `DATABASE_MAPPING` keyed by the URL product slug; users cannot target an arbitrary database |

---

## Troubleshooting

### Ollama not responding

```bash
# Start the server
ollama serve

# Verify it responds
curl http://localhost:11434/api/tags
```

### "Product not found in metadata"

The product key in the URL does not match a key under `datasets` in `metadata.json`. All keys are case-sensitive. Ensure the same string appears in:

- The URL: `/sql-search/<key>`
- `DATABASE_MAPPING` in `app_34.py`
- `PROMPT_FOLDER_MAPPING` in `app_34.py`
- `metadata.json` under `datasets`

### No indicator detected / blank indicator returned

Either the query is semantically too far from any indicator in `metadata.json`, or the indicators list for that product is empty. Fix: broaden or add more indicator name variants in `metadata.json`.

### "relation data_view does not exist"

The PostgreSQL database for this product does not have a `data_view` table or view. Either create the view in the database, or reference the correct table name in your prompt template.

### Results are wrong or too broad

Check `performance.json` for the most recent entry:

1. Was the correct `indicator` detected? → fix `metadata.json` indicator names if not
2. Does `distinct_relevant_values` match your expectation? → fix filter extraction prompt if not
3. Is the `final_sql_used` WHERE clause correct? → fix SQL generation prompt if not

### App crashes on startup

```bash
# Verify all packages are installed
pip install dash dash-bootstrap-components plotly pandas psycopg2-binary requests

# Validate metadata.json is valid JSON
python -c "import json; json.load(open('metadata.json')); print('OK')"

# Verify prompts/common/ has both required files
ls prompts/common/
# Expected: aggregation.prompt  non_aggregation.prompt
```

### Query times out

The default statement timeout is 60 seconds. For very broad queries:

- Add more specific filters in your question
- Increase the timeout in `execute_query()`: change `timeout_seconds=60` to `timeout_seconds=120`
- Add an index on the `indicator` column in your database:

```sql
CREATE INDEX idx_indicator ON data_view (indicator);
```
