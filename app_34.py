import json
import requests
import time
import difflib
import re
import psycopg2
from psycopg2.pool import SimpleConnectionPool
import os
from decimal import Decimal

# =========================
# LLM CONFIG
# =========================
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3:70b"
OLLAMA_TIMEOUT = 120
OLLAMA_TEMPERATURE = 0

# Determinism settings — applied to every LLM call.
# seed + temperature=0 + top_p=1 + top_k=1 guarantees identical
# outputs for identical inputs across all Ollama requests.
OLLAMA_SEED = 42
OLLAMA_TOP_P = 1
OLLAMA_TOP_K = 1

# =========================
# DATABASE MAPPING
# =========================
DATABASE_MAPPING = {
    "gender": "gender_db",
    "envstat": "env_db",
    "iip": "iip_db",
    "cpialrl": "cpialrl_db",
    "cpi": "cpi_db",
    "cpi_grp": "cpi2_db",
    "cpi_itm": "cpi2_db",
    "cpi_24":  "cpi2_db",
    "tus": "tus_db",
    "hces": "hces_db",
    "esi": "energy_db",
    "plfs": "plfs_db",
    "asi": "asi_db",
    "nas": "nas_db",
    "aishe": "aishe_db",
    "wpi": "wpi_db",
    "asuse": "asuse_db",
    "nfhs": "nfhs_db",
    "rbi": "rbi_db",
    "nss77": "nss_77_db",
    "nss78": "nss_78_db",
    "nss79": "nss79_db"
}

# =========================
# PROMPT FOLDER MAPPING
# Each CPI sub-product has its own dedicated prompt folder.
# =========================
PROMPT_FOLDER_MAPPING = {
    "gender":  "gender",
    "envstat": "envstat",
    "iip":     "iip",
    "cpialrl": "cpialrl",
    "cpi":     "cpi",
    "cpi_grp": "cpi_grp",
    "cpi_itm": "cpi_itm",
    "cpi_24":  "cpi_24",
    "tus":     "tus",
    "hces":    "hces",
    "esi":     "esi",
    "plfs":    "plfs",
    "asi":     "asi",
    "nas":     "nas",
    "aishe":   "aishe",
    "asuse":   "asuse",
    "nfhs":    "nfhs",
    "rbi":     "rbi",
    "wpi":     "wpi",
    "nss77":   "nss77",
    "nss78":   "nss78",
    "nss79":   "nss79"
}

# =========================
# CPI: data_view table name per sub-product
# =========================
CPI_DATA_VIEW_MAPPING = {
    "cpi_grp": "data_view_grp",
    "cpi_itm": "data_view_itm",
    "cpi_24":  "data_view_24",
}

# =========================
# FALLBACK VALUE COLUMNS per product
# These are the measure/value columns selected in fallback queries.
# =========================
FALLBACK_VALUE_COLUMNS = {
    "cpi_grp": "index, inflation",
    "cpi_itm": "index, inflation",
    "cpi_24":  "index, inflation",
    "cpialrl": "index_al, index_rl, inflation_al, inflation_rl",
    "envstat": "value",
    "asi":     "value",
    
}
FALLBACK_VALUE_COLUMNS_DEFAULT = "indicator_value"

# =========================
# PRINT HELPERS
# =========================
def print_section(title, content=""):
    print(f"\n{'='*60}", flush=True)
    print(f"  {title}", flush=True)
    print(f"{'='*60}", flush=True)
    if content:
        print(content, flush=True)

def print_divider():
    print("-" * 60, flush=True)

# =========================
# LOAD JSON
# =========================
def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as file:
        return json.load(file)

# =========================
# EXTRACT INDICATORS
# =========================
def extract_indicators(product_name, data):
    datasets = data.get("datasets", {})
    for dataset_key in datasets:
        if dataset_key.lower() == product_name.lower():
            return datasets[dataset_key].get("indicators", [])
    return []

# =========================
# CPI PRODUCT ROUTING
# Determines the correct CPI sub-product (cpi_grp / cpi_itm / cpi_24)
# from the user query. Called only when the incoming product == "cpi".
# =========================
def resolve_cpi_sub_product(user_query):
    """
    Condition 1: query mentions group/grp/groups AND any year before 2018  -> cpi_grp
    Condition 2: query mentions any year before 2018 (no group keywords)   -> cpi_itm
    Default:                                                                -> cpi_24
    """
    query_lower = user_query.lower()

    years_in_query    = [int(y) for y in re.findall(r'\b(19\d{2}|20\d{2})\b', query_lower)]
    has_pre_2018_year = any(y < 2018 for y in years_in_query)
    has_group_keyword = bool(re.search(r'\b(group|grp|groups)\b', query_lower))

    if has_group_keyword and has_pre_2018_year:
        product_name = "cpi_grp"
    elif has_pre_2018_year:
        product_name = "cpi_itm"
    else:
        product_name = "cpi_24"

    print(f"\n[CPI ROUTING] years_found={years_in_query}, has_pre_2018={has_pre_2018_year}, "
          f"has_group_kw={has_group_keyword} -> product_name={product_name}", flush=True)
    return product_name

# =========================
# INDICATOR DETECTION
# =========================
def get_indicator(user_query, indicators, product_name):
    indicator_names = [i["indicator_name"].strip() for i in indicators]

    prompt = f"""
    You are an expert semantic matching engine.

    TASK:
    From the provided indicator list, select the ONE indicator
    that is most semantically similar to the user query.

    CRITICAL RULES:
    1. You MUST choose only from the provided list.
    2. Do NOT modify indicator text.
    3. Do NOT create new indicator.
    4. Do NOT return partial text.
    5. If multiple indicators look similar, choose the one with the highest semantic similarity.
    6. The match must be extremely close to user intent.
    7. If user query and indicators are entirely different then give indicator blank in json
    User Query:
    \"\"\"{user_query}\"\"\"

    Available Indicators:
    {json.dumps(indicator_names, indent=2)}

    Think carefully:
    - Compare meaning, not just keywords.
    - Consider singular/plural forms.
    - Consider synonyms.
    - Prefer exact domain match over partial keyword overlap.

    Return ONLY valid JSON:
    {{
    "indicator": ""
    }}

    CRITICAL: Always give indicator from the list in exact same format as in given list if indicator has white spaces keep it as it is, do not remove or add anything in selected indicator

   Product Specific Rules:
    Product:{product_name}
    CRITICAL:
    if product recieved is CPIALRL then by default indicator is Group Index and if user mention either General in prompt or user_query is generic like , inflation in india in some year or inflation in a state etc. then indicator is General Index.
    if poduct is other then CPIALRL then give indicator from the above list whic is most relevant to  user query which is : {user_query}
    No explanation. No extra text.Dont ask question, Only JSON output.
    """

    print_section("INDICATOR DETECTION -- PROMPT SENT TO LLM")
    print(prompt)

    # --- DETERMINISTIC: temperature=0 + seed + top_p + top_k ---
    payload = {
        "model":       OLLAMA_MODEL,
        "prompt":      prompt,
        "stream":      False,
        "temperature": OLLAMA_TEMPERATURE,
        "seed":        OLLAMA_SEED,
        "top_p":       OLLAMA_TOP_P,
        "top_k":       OLLAMA_TOP_K,
    }
    response = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT)
    raw      = response.json().get("response", "").strip()

    print_section("INDICATOR DETECTION -- RAW LLM OUTPUT")
    print(raw)

    try:
        start  = raw.find("{")
        end    = raw.rfind("}") + 1
        result = json.loads(raw[start:end])
    except:
        print("[ERROR] Failed to parse indicator JSON from LLM output.")
        return ""

    indicator = result.get("indicator", "").strip()

    if indicator not in indicator_names:
        match = difflib.get_close_matches(indicator, indicator_names, n=1)
        if match:
            print(f"[FUZZY MATCH] LLM returned '{indicator}' -> matched to '{match[0]}'")
            indicator = match[0]

    print_section("INDICATOR IDENTIFIED")
    print(f"  >>> {indicator}")

    return indicator

# =========================
# AGGREGATION DETECTION
# =========================
def detect_aggregation_from_query(user_query):
    aggregation_keywords = ["average", "total", "sum", "mean"]
    query_lower = user_query.lower()
    for word in aggregation_keywords:
        if word in query_lower:
            print(f"\n[AGGREGATION] Detected keyword '{word}' -> aggregation = YES")
            return "yes"
    print("\n[AGGREGATION] No aggregation keyword found -> aggregation = NO")
    return "no"

# =========================
# FILTER EXTRACTION
# =========================
def get_filters_json(indicator_name, indicators):
    for item in indicators:
        if item["indicator_name"].strip() == indicator_name.strip():
            filters = {}
            for block in item.get("filters", []):
                for key, values in block.items():
                    filters[key] = values
            return filters
    return {}

# =========================
# FILTER ANALYSIS
# =========================
def analyze_filters_with_llm(user_query, indicator_metadata):
    prompt = f"""
You are a strict schema-based filter extraction engine. You only extract. You never invent.

AVAILABLE COLUMNS WITH DISTINCT VALUES:
{json.dumps(indicator_metadata, indent=2)}

USER QUERY:
'''{user_query}'''

STEP-BY-STEP INSTRUCTIONS (follow in order):

STEP 1 - IDENTIFY RELEVANT COLUMNS
- A column is relevant ONLY if the user query references it directly or implicitly.
- Use ONLY column names that exist in AVAILABLE COLUMNS. Never invent column names.
- a column named as year or year as part part of column name example: year, financial_year, release_year, base_year etc. then these are essentially relevant column , whether it is mentioned in prompt or not.

STEP 2 - EXTRACT VALUES (ONLY FROM SCHEMA)
- For each relevant column, pick ONLY the specific values from schema that match what the user is asking.
- If user references a SPECIFIC value (e.g. "mens", "rural", "Bihar") -> extract ONLY that matching or similar value from schema, not all values.
- If user specifies a RANGE -> include only schema values that fall within that range.
- If user specifies a value NOT in schema -> use the closest matching schema value.
- If user query is GENERIC for a column (no specific value mentioned) -> include ALL distinct values for that column.
- NEVER invent, guess, or paraphrase values. NEVER include extra values the user did not ask for.
- Example: user asks "population of mens in India"
    -> gender column: ["Male"] (only the matching schema value for "mens")
    -> state column: ["All India"] (only the matching schema value for "India")
- If user do not mention the year and there is a key one or more of year, financial_year,base_year, release_year etc. (term with year), then essentially keep it as relevant column keep most recent year in the value for all keys having year

STEP 3 - YEAR FALLBACK (apply strictly)
- If user mentions a year NOT in schema -> use the numerically closest available year.
- If user does NOT mention any year -> automatically use the latest available year in schema.
- NEVER output a year that is not in schema.

STEP 4 - GEOGRAPHY FALLBACK (apply strictly in this priority order)
- If user mentions a city:
    -> First check: is that city's STATE available in schema? If yes -> use that state.
    -> Else check: is "All India" available in schema? If yes -> use "All India".
    -> Else -> use whatever geographic level exists in schema.
- If user says "India" or "all India":
    -> Check if "All India" exists in the state column if yes -> use it.
    -> Else -> include all actual state values from schema.

- CRITICAL: If user say India or All India data and if in state column All India is not available then give all state in state column, and do not take all india
- NEVER invent a geography value. NEVER use a value not in schema.

STEP 5 - TOP N / BOTTOM N RULE
- If user asks for "top N states", "bottom N states", "highest N", "lowest N", or similar rankings:
    -> Include ALL distinct values from the states column. Do not filter or rank.
    -> The SQL layer will handle ranking. Your job is only relevance + schema values.

STEP 6 - BUILD modified_query
- Rewrite the user query replacing any value NOT in schema with the actual matched schema value.
- modified_query must ONLY contain terms that exist in relevant_data values or are neutral words.
- NEVER include invented terms, original out-of-schema values, or column names in modified_query.
- If all user values matched schema exactly -> modified_query = original user query unchanged.
- Examples:
    User: "Fertility rate in 2025 in Haridwar" | Schema year: 2022, Schema state: Uttarakhand
    -> modified_query: "Fertility rate in 2022 in Uttarakhand"

    User: "Fertility rate in 2025 in Haridwar" | Schema year: 2015, Schema state: All India
    -> modified_query: "Fertility rate in 2015 in All India"

    User: "population of mens in India" | Schema gender: Male, Schema state: All India
    -> modified_query: "population of Male in All India"

OUTPUT FORMAT - STRICT
Return ONLY the following JSON. No explanation. No markdown. No extra text. No code fences.

{{
  "relevant_data": {{
    "column_name": ["value1", "value2"]
  }},
  "modified_query": "rewritten prompt using only schema values"
}}

FINAL CHECKS BEFORE OUTPUT:
- Every key in relevant_data -> must be a column name from AVAILABLE COLUMNS.
- Every value in relevant_data -> must be a value from that column's distinct list in AVAILABLE COLUMNS.
- Only include schema values the user actually asked for - do NOT pad with extra values.
- modified_query -> contains zero invented terms.
- If user do not mention the year and there is a key one or more of year, financial_year,base_year, release_year etc. (term with year), then essentially keep it is a relevant column keep most recent year in the value for all keys having year
- Output is valid JSON only. Nothing else.
"""

    print_section("FILTER ANALYSIS -- PROMPT SENT TO LLM")
    print(prompt)

    # --- DETERMINISTIC: temperature=0 + seed + top_p + top_k ---
    payload = {
        "model":       OLLAMA_MODEL,
        "prompt":      prompt,
        "stream":      False,
        "temperature": OLLAMA_TEMPERATURE,
        "seed":        OLLAMA_SEED,
        "top_p":       OLLAMA_TOP_P,
        "top_k":       OLLAMA_TOP_K,
    }
    response = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT)
    raw      = response.json().get("response", "").strip()

    print_section("FILTER ANALYSIS -- RAW LLM OUTPUT")
    print(raw)

    try:
        start  = raw.find("{")
        end    = raw.rfind("}") + 1
        result = json.loads(raw[start:end])
    except:
        print("[ERROR] Failed to parse filter JSON from LLM output.")
        result = {"relevant_data": {}, "non_relevant_columns": [], "modified_query": user_query}

    filters = {}
    for col, values in result.get("relevant_data", {}).items():
        filters[col] = values if isinstance(values, list) else [values]

    non_rel        = []
    modified_query = result.get("modified_query", user_query).strip()
    if not modified_query:
        modified_query = user_query

    print_section("FILTER ANALYSIS -- EXTRACTED RESULTS")
    print(f"  Relevant Columns    : {list(filters.keys())}")
    print_divider()
    print(f"  Non-Relevant Columns: {non_rel}")
    print_divider()
    print("  Distinct Values per Relevant Column:")
    for col, vals in filters.items():
        print(f"    [{col}] -> {vals}")
    print_divider()
    print(f"  Original Query  : {user_query}")
    print(f"  Modified Query  : {modified_query}")

    return {"filters": filters, "non_rel_column": non_rel, "modified_query": modified_query}

# =========================
# LOAD PROMPT TEMPLATE
# Every product (including CPI sub-products) uses:
#   aggregation.prompt     when aggregation == "yes"
#   non_aggregation.prompt otherwise
# from its own dedicated folder defined in PROMPT_FOLDER_MAPPING.
# =========================
def load_prompt_template(product, is_aggregation):
    folder_name = PROMPT_FOLDER_MAPPING.get(product, product.lower())
    prompt_file = "aggregation.prompt" if is_aggregation == "yes" else "non_aggregation.prompt"

    product_path = os.path.join("prompts", folder_name, prompt_file)
    common_path  = os.path.join("prompts", "common", prompt_file)

    if os.path.exists(product_path):
        path        = product_path
        used_folder = folder_name
    elif os.path.exists(common_path):
        path        = common_path
        used_folder = "common"
    else:
        raise FileNotFoundError(
            f"Prompt file not found at '{product_path}' or '{common_path}'. "
            f"product='{product}', folder='{folder_name}', file='{prompt_file}'"
        )

    with open(path, "r", encoding="utf-8") as f:
        template = f.read()

    return template, used_folder, prompt_file

# =========================
# SQL GENERATION
# =========================
def generate_sql_with_llm(product, user_query, modified_query, indicator,
                           relevant_data, non_relevant_columns,
                           indicator_metadata, is_aggregation):
    relevant_columns = list(relevant_data.keys())
    select_columns   = relevant_columns + non_relevant_columns

    where_conditions = ""
    for col, values in relevant_data.items():
        formatted = ", ".join([f"'{v}'" for v in values])
        where_conditions += f"{col} IN ({formatted})\n"

    template, used_folder, prompt_file = load_prompt_template(product, is_aggregation)

    print_section("SQL GENERATION -- QUERY USED")
    print(f"  Original Query : {user_query}")
    print(f"  Modified Query : {modified_query}")

    prompt = (
        template
        .replace("$modified_query",       modified_query)
        .replace("$indicator",            indicator)
        .replace("$relevant_columns",     json.dumps(relevant_columns, indent=2))
        .replace("$non_relevant_columns", json.dumps(non_relevant_columns, indent=2))
        .replace("$matched_values",       json.dumps(relevant_data, indent=2))
        .replace("$select_columns",       json.dumps(select_columns, indent=2))
        .replace("$where_conditions",     where_conditions)
    )

    print_section(f"SQL GENERATION -- PROMPT SENT TO LLM  [{used_folder}/{prompt_file}]")
    print(prompt)

    # --- DETERMINISTIC: temperature=0 + seed + top_p + top_k ---
    # NOTE: stream=True is kept for SQL generation (long output) but
    # seed is still honoured by Ollama in streaming mode.
    payload = {
        "model":       OLLAMA_MODEL,
        "prompt":      prompt,
        "stream":      True,
        "temperature": OLLAMA_TEMPERATURE,
        "seed":        OLLAMA_SEED,
        "top_p":       OLLAMA_TOP_P,
        "top_k":       OLLAMA_TOP_K,
    }
    response = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, stream=True)

    sql_query = ""
    for line in response.iter_lines():
        if line:
            chunk = json.loads(line.decode("utf-8"))
            sql_query += chunk.get("response", "")

    sql_query = sql_query.strip()

    print_section("SQL GENERATION -- RAW LLM OUTPUT")
    print(sql_query)

    return sql_query, used_folder, prompt_file

# =========================
# INDICATOR LIKE WILDCARD REWRITE
# =========================
def build_indicator_like_pattern(indicator_name):
    tokens = [t for t in re.split(r'\s+', indicator_name) if t]
    return '%' + '%'.join(tokens) + '%'

def ensure_indicator_present(normalized_conditions, indicator_name):
    has_indicator = False

    for cond in normalized_conditions:
        # IMPORTANT: avoid sub_indicator
        if re.match(r'^\s*indicator\s+(?:LIKE|=)', cond, re.IGNORECASE):
            has_indicator = True
            break

    if not has_indicator:
        like_pattern = build_indicator_like_pattern(indicator_name)
        new_condition = f"indicator LIKE '{like_pattern}'"
        print(f"  [INDICATOR ADD] No indicator found -> adding: {new_condition}")
        normalized_conditions.append(new_condition)

    return normalized_conditions

def rewrite_indicator_condition_in_sql(sql_query, canonical_indicator):
    like_pattern = build_indicator_like_pattern(canonical_indicator)
    indicator_re = re.compile(r"indicator\s+(?:LIKE|=)\s+'[^']*'", re.IGNORECASE)
    replacement  = f"indicator LIKE '{like_pattern}'"
    new_sql, count = indicator_re.subn(replacement, sql_query)
    if count:
        print(f"  [INDICATOR REWRITE] Replaced {count} indicator condition(s) -> {replacement}")
    else:
        print("  [INDICATOR REWRITE] No indicator condition found to rewrite.")
    return new_sql

# =========================
# NORMALIZE SQL WHERE CLAUSE
# =========================
def normalize_sql_where_clause(sql_query, indicator_name, filters_meta):
    print_section("WHERE NORMALIZATION -- INPUT SQL")
    print(sql_query)
    print(f"\n  Indicator  : {indicator_name}")
    print(f"  Metadata   : {json.dumps(filters_meta, indent=4)}")

    where_split = re.split(r'\bWHERE\b', sql_query, maxsplit=1, flags=re.IGNORECASE)

    if len(where_split) < 2:
        print("  [NORMALIZE] No WHERE clause found -- returning SQL unchanged.")
        return rewrite_indicator_condition_in_sql(sql_query, indicator_name)

    pre_where   = where_split[0].rstrip()
    where_block = where_split[1]

    trailing_match = re.split(
        r'\b(GROUP\s+BY|ORDER\s+BY|LIMIT|HAVING)\b',
        where_block, maxsplit=1, flags=re.IGNORECASE
    )
    raw_conditions_str = trailing_match[0]
    trailing_clause    = "".join(trailing_match[1:]) if len(trailing_match) > 1 else ""

    def split_and_conditions(text):
        conditions = []
        depth   = 0
        current = ""
        i       = 0
        upper   = text.upper()
        while i < len(text):
            if text[i] == '(':
                depth += 1
                current += text[i]
            elif text[i] == ')':
                depth -= 1
                current += text[i]
            elif upper[i:i+4] == ' AND' and depth == 0 and i + 4 < len(text):
                after = text[i+4:i+5]
                if after in (' ', '\n', '\t', '('):
                    conditions.append(current.strip())
                    current = ""
                    i += 4
                    continue
                else:
                    current += text[i]
            else:
                current += text[i]
            i += 1
        if current.strip():
            conditions.append(current.strip())
        return conditions

    raw_conditions = split_and_conditions(raw_conditions_str)

    print_section("WHERE NORMALIZATION -- PARSED CONDITIONS")
    for idx, c in enumerate(raw_conditions):
        print(f"  [{idx}] {c.strip()}")

    def fuzzy_match_value(raw_val, valid_values, cutoff=0.6):
        raw_stripped = raw_val.strip().strip("'\"").lower()
        for v in valid_values:
            if v.lower().rstrip('*') == raw_stripped.rstrip('*'):
                return v
            if v.lower() == raw_stripped:
                return v
        clean_valid = [v.rstrip('*') for v in valid_values]
        matches = difflib.get_close_matches(raw_stripped.rstrip('*'), clean_valid, n=1, cutoff=cutoff)
        if matches:
            matched_clean = matches[0]
            for v in valid_values:
                if v.rstrip('*') == matched_clean:
                    return v
        return None

    normalized_conditions = []

    for condition in raw_conditions:
        condition = condition.strip().rstrip(',').strip()
        if not condition:
            continue

        # -------------------------------------------------------
        # INDICATOR condition -- rewrite with canonical wildcard
        # -------------------------------------------------------
        if re.match(r'^indicator\s+(?:LIKE|=)\s*(.+)$', condition, re.IGNORECASE):
            like_pattern = build_indicator_like_pattern(indicator_name)
            rewritten    = f"indicator LIKE '{like_pattern}'"
            normalized_conditions.append(rewritten)
            print(f"  [NORMALIZE] indicator condition -> {rewritten}")
            continue

        # -------------------------------------------------------
        # col IN ('v1', 'v2', ...)
        # -------------------------------------------------------
        in_match = re.match(
            r'^"?(\w+)"?\s+IN\s*\((.+)\)\s*$',
            condition, re.IGNORECASE | re.DOTALL
        )
        if in_match:
            col_name   = in_match.group(1).strip().lower()
            values_str = in_match.group(2).strip()
            raw_values = [
                v.strip().strip("'\"")
                for v in re.split(r',\s*', values_str)
                if v.strip().strip("'\"")
            ]
            non_empty_raws = [v for v in raw_values if v.strip()]
            if not non_empty_raws:
                print(f"  [NORMALIZE] Column '{col_name}' -- all values blank -> REMOVING condition")
                continue
            valid_values = filters_meta.get(col_name, [])
            if not valid_values:
                print(f"  [NORMALIZE] Column '{col_name}' not in metadata -> REMOVING condition")
                continue
            matched = []
            for rv in non_empty_raws:
                best = fuzzy_match_value(rv, valid_values)
                if best:
                    print(f"  [NORMALIZE] '{col_name}': '{rv}' -> matched '{best}'")
                    matched.append(best)
                else:
                    print(f"  [NORMALIZE] '{col_name}': '{rv}' -> NO match found, skipping")
            if not matched:
                print(f"  [NORMALIZE] Column '{col_name}' -- no valid matches -> REMOVING condition")
                continue
            seen    = set()
            deduped = []
            for m in matched:
                if m not in seen:
                    seen.add(m)
                    deduped.append(m)
            formatted_vals = ", ".join([f"'{v}'" for v in deduped])
            normalized_conditions.append(f"{col_name} IN ({formatted_vals})")
            continue

        # -------------------------------------------------------
        # col = 'value'
        # -------------------------------------------------------
        eq_match = re.match(
            r'^"?(\w+)"?\s*=\s*\'([^\']*)\'\s*$',
            condition, re.IGNORECASE
        )
        if eq_match:
            col_name = eq_match.group(1).strip().lower()
            raw_val  = eq_match.group(2).strip()
            if not raw_val:
                print(f"  [NORMALIZE] Column '{col_name}' = empty -> REMOVING condition")
                continue
            valid_values = filters_meta.get(col_name, [])
            if not valid_values:
                print(f"  [NORMALIZE] Column '{col_name}' not in metadata -> REMOVING condition")
                continue
            best = fuzzy_match_value(raw_val, valid_values)
            if best:
                print(f"  [NORMALIZE] '{col_name}': '{raw_val}' -> matched '{best}'")
                normalized_conditions.append(f"{col_name} = '{best}'")
            else:
                print(f"  [NORMALIZE] '{col_name}': '{raw_val}' -> NO match -> REMOVING condition")
            continue

        # -------------------------------------------------------
        # Anything else (garbled/partial SQL from LLM) -> REMOVE
        # Never pass unrecognized fragments into the final query.
        # -------------------------------------------------------
        print(f"  [NORMALIZE] Unrecognized condition format -> REMOVING: {condition}")
        # intentionally NOT appending to normalized_conditions
    normalized_conditions = ensure_indicator_present(normalized_conditions, indicator_name)

    if normalized_conditions:
        new_where      = " AND ".join(normalized_conditions)
        normalized_sql = f"{pre_where} WHERE {new_where}"
    else:
        print("  [NORMALIZE] WARNING: All WHERE conditions removed. Running without WHERE.")
        normalized_sql = pre_where

    if trailing_clause.strip():
        normalized_sql += f" {trailing_clause.strip()}"

    print_section("WHERE NORMALIZATION -- NORMALIZED SQL")
    print(normalized_sql)

    return normalized_sql


# =========================
# READ-ONLY QUERY GUARD
# =========================
def is_read_only_query(sql_query):
    cleaned = re.sub(r'--[^\n]*', ' ', sql_query)
    cleaned = re.sub(r'/\*.*?\*/', ' ', cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    return bool(re.match(r'^\s*SELECT\b', cleaned, re.IGNORECASE))


# =========================
# SQL CORRECTION (RETRY MAX 3)
# =========================
def retry_sql_correction(product, modified_query, indicator, sql_query, error_message,
                          relevant_columns, non_relevant_columns, original_prompt,
                          is_aggregation, filters_meta, max_attempts=3):
    attempt       = 1
    corrected_sql = sql_query
    retry_history = []

    while attempt <= max_attempts:
        correction_prompt = f"""
You are a PostgreSQL expert.

The previous SQL query failed.

User Prompt: {modified_query}
Indicator: {indicator}
Relevant Columns: {json.dumps(relevant_columns, indent=2)}
Non Relevant Columns: {json.dumps(non_relevant_columns, indent=2)}
Previous SQL: {corrected_sql}
Database Error: {error_message}

Fix the SQL query. Return ONLY corrected SQL.
IMPORTANT RULE:
Only give one sql query
No markdown, not extra explanation, no quotes, nothing except sql query from SELECT till complete SQL query.
OUTPUT RULES (CRITICAL):

- Output must begin with SELECT
- Output must end with semicolon
- No explanation
- No markdown
- No text before SELECT
- No text after semicolon
- No comments
- Only one SQL query
"""

        print_section(f"SQL RETRY -- ATTEMPT {attempt} -- PROMPT SENT TO LLM")
        print(correction_prompt)

        # --- DETERMINISTIC: temperature=0 + seed + top_p + top_k ---
        # NOTE: stream=True kept for consistency with SQL generation.
        payload = {
            "model":       OLLAMA_MODEL,
            "prompt":      correction_prompt,
            "stream":      True,
            "temperature": OLLAMA_TEMPERATURE,
            "seed":        OLLAMA_SEED,
            "top_p":       OLLAMA_TOP_P,
            "top_k":       OLLAMA_TOP_K,
        }
        response = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, stream=True)

        new_sql = ""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line.decode("utf-8"))
                new_sql += chunk.get("response", "")

        corrected_sql = new_sql.strip()

        print_section(f"SQL RETRY -- ATTEMPT {attempt} -- LLM OUTPUT")
        print(corrected_sql)

        corrected_sql    = normalize_sql_where_clause(corrected_sql, indicator, filters_meta)
        corrected_sql = enforce_limit(corrected_sql)
        result, db_error = execute_query(product, corrected_sql)
        

        if db_error:
            print(f"\n[RETRY {attempt}] DB Error: {db_error}")
        else:
            print(f"\n[RETRY {attempt}] Query executed successfully.")

        retry_history.append({
            "attempt":       attempt,
            "prompt_used":   correction_prompt,
            "generated_sql": corrected_sql,
            "error":         db_error
        })

        if not db_error:
            return corrected_sql, result, None, retry_history

        error_message = db_error
        attempt += 1

    return None, None, error_message, retry_history


# =========================
# FALLBACK QUERY -- DYNAMIC
# Columns  : all filter keys from indicator metadata + product-specific value columns
# Table    : data_view_grp / data_view_itm / data_view_24 for CPI; data_view for all others
# Order by : first year-like column; first column otherwise
# =========================
def generate_fallback_query(product, indicator, filters_meta):
    table_name      = CPI_DATA_VIEW_MAPPING.get(product, "data_view")
    all_filter_keys = list(filters_meta.keys())
    value_cols      = FALLBACK_VALUE_COLUMNS.get(product, FALLBACK_VALUE_COLUMNS_DEFAULT)

    select_part  = (", ".join(all_filter_keys) + f", {value_cols}") if all_filter_keys else f"{value_cols}"
    like_pattern = build_indicator_like_pattern(indicator)

    year_cols = [k for k in all_filter_keys if "year" in k.lower()]
    order_col = year_cols[0] if year_cols else (all_filter_keys[0] if all_filter_keys else "1")

    fallback_sql = (
        f"SELECT {select_part}\n"
        f"FROM {table_name}\n"
        f"WHERE indicator LIKE '{like_pattern}'\n"
        f"ORDER BY {order_col}\n"
        f"LIMIT 100;"
    )

    print_section("FALLBACK QUERY -- GENERATED")
    print(fallback_sql)
    return fallback_sql


# =========================
# DB POOL
# =========================
db_pools = {}

def get_db_pool(db_name):
    if db_name not in db_pools:
        db_pools[db_name] = SimpleConnectionPool(
            2, 5,
            host="103.48.43.11",
            port=5432,
            user="postgres",
            password="root456",
            database=db_name
        )
    return db_pools[db_name]
def enforce_limit(sql_query, default_limit=500):
    if re.search(r'\bLIMIT\b\s+\d+', sql_query, re.IGNORECASE):
        print("[LIMIT] Existing LIMIT found -> no change")
        return sql_query

    print(f"[LIMIT] No LIMIT found -> adding LIMIT {default_limit}")
    sql_query = sql_query.strip().rstrip(";")
    return f"{sql_query}\nLIMIT {default_limit};"
# =========================
# EXECUTE QUERY (60-second timeout)
# =========================
def execute_query(product, sql_query, timeout_seconds=60):
    if not is_read_only_query(sql_query):
        msg = (
            "Invalid query. You are not allowed to modify the database. "
            "Only SELECT (retrieval) queries are permitted."
        )
        print(f"\n[SECURITY] Read-only guard triggered. Query rejected:\n{sql_query}")
        return [], msg

    db_name = DATABASE_MAPPING.get(product)
    if not db_name:
        return [], f"No database mapping found for product '{product}'"

    pool = get_db_pool(db_name)
    conn = None

    try:
        conn   = pool.getconn()
        cursor = conn.cursor()

        cursor.execute(f"SET statement_timeout = {timeout_seconds * 1000};")
        cursor.execute(sql_query)

        if cursor.description:
            columns = [desc[0] for desc in cursor.description]
            rows    = cursor.fetchall()
            results = []
            for row in rows:
                row_dict = {}
                for col, val in zip(columns, row):
                    row_dict[col] = float(val) if isinstance(val, Decimal) else val
                results.append(row_dict)
        else:
            results = []

        cursor.close()
        return results, None

    except Exception as e:
        err_str = str(e)
        if "canceling statement due to statement timeout" in err_str or "statement_timeout" in err_str:
            return [], f"Query timed out after {timeout_seconds} seconds. Please refine your query."
        return [], err_str

    finally:
        if conn:
            pool.putconn(conn)

# =========================
# PERFORMANCE LOGGER
# =========================
def log_performance(data):
    filepath = "performance.json"
    logs     = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except:
            logs = []
    logs.append(data)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4, ensure_ascii=False)

# =========================
# VALIDATE PRODUCT
# =========================
def validate_product(product_name, indicators):
    return len(indicators) > 0

# =========================
# GET INDICATOR FILTERS (for UI info panel)
# =========================
def get_indicator_filters_for_display(product_name, indicator_name):
    try:
        metadata   = load_json("metadata.json")
        indicators = extract_indicators(product_name, metadata)
        return get_filters_json(indicator_name, indicators)
    except Exception:
        return {}

# =========================
# PROCESS QUERY (UI ENTRY POINT)
# =========================
def process_query(user_query, product_name):
    print_section("NEW QUERY RECEIVED")
    print(f"  Product    : {product_name}")
    print(f"  User Query : {user_query}")

    # ------------------------------------------------------------------
    # CPI ROUTING -- resolve sub-product before any metadata look-up
    # ------------------------------------------------------------------
    if product_name.lower() == "cpi":
        product_name = resolve_cpi_sub_product(user_query)
        print(f"  [CPI] Resolved sub-product -> {product_name}", flush=True)

    metadata   = load_json("metadata.json")
    indicators = extract_indicators(product_name, metadata)

    if not indicators:
        print(f"\n[ERROR] Product '{product_name}' not found in metadata.")
        return {
            "success":    False,
            "error":      f"Product '{product_name}' not found.",
            "error_type": "DATASET_MISMATCH"
        }

    indicator = get_indicator(user_query, indicators, product_name)
    if not indicator:
        print("\n[ERROR] Indicator could not be detected.")
        return {"success": False, "error": "Could not detect indicator from query."}

    is_agg       = detect_aggregation_from_query(user_query)
    filters_meta = get_filters_json(indicator, indicators)
    analysis     = analyze_filters_with_llm(user_query, filters_meta)

    all_columns          = set(filters_meta.keys())
    relevant_columns     = set(analysis["filters"].keys())
    non_relevant_columns = list(all_columns - relevant_columns)
    analysis["non_rel_column"] = non_relevant_columns

    print_section("SUMMARY BEFORE SQL GENERATION")
    print(f"  Indicator            : {indicator}")
    print(f"  Aggregation          : {is_agg}")
    print(f"  Original Query       : {user_query}")
    print(f"  Modified Query       : {analysis.get('modified_query', user_query)}")
    print(f"  Relevant Columns     : {list(analysis['filters'].keys())}")
    print(f"  Non-Relevant Columns : {analysis['non_rel_column']}")
    print("  Distinct Values:")
    for col, vals in analysis["filters"].items():
        print(f"    [{col}] -> {vals}")

    modified_query = analysis.get("modified_query", user_query)

    # ------------------------------------------------------------------
    # SQL GENERATION -- explicit try/except so errors appear on terminal
    # ------------------------------------------------------------------
    try:
        sql_query, used_folder, prompt_file = generate_sql_with_llm(
            product_name, user_query, modified_query, indicator,
            analysis["filters"], analysis["non_rel_column"],
            filters_meta, is_agg
        )
    except Exception as exc:
        print(f"\n[FATAL] SQL generation failed: {exc}", flush=True)
        return {"success": False, "error": f"SQL generation failed: {exc}"}

    sql_query = normalize_sql_where_clause(sql_query, indicator, filters_meta)
    sql_query = enforce_limit(sql_query)

    all_sql_history   = [{"type": "initial", "sql": sql_query}]
    all_error_history = []

    print_section("EXECUTING INITIAL SQL")
    print(sql_query)

    result, db_error = execute_query(product_name, sql_query)

    if db_error:
        print(f"\n[DB ERROR] {db_error}")
        all_error_history.append({"type": "initial", "error": db_error})

        try:
            template, _, _ = load_prompt_template(product_name, is_agg)
            original_prompt = (template
                               .replace("$modified_query", modified_query)
                               .replace("$indicator", indicator))
        except:
            original_prompt = ""

        print_section("INITIATING SQL RETRY CORRECTION")

        corrected_sql, result, retry_error, retry_history = retry_sql_correction(
            product=product_name,
            modified_query=modified_query,
            indicator=indicator,
            sql_query=sql_query,
            error_message=db_error,
            relevant_columns=list(analysis["filters"].keys()),
            non_relevant_columns=analysis["non_rel_column"],
            original_prompt=original_prompt,
            is_aggregation=is_agg,
            filters_meta=filters_meta
        )

        for r in retry_history:
            all_sql_history.append({"type": f"retry_attempt_{r['attempt']}", "sql": r["generated_sql"]})
            if r["error"]:
                all_error_history.append({"type": f"retry_attempt_{r['attempt']}", "error": r["error"]})

        if corrected_sql:
            sql_query = corrected_sql
            db_error  = None
            print_section("RETRY SUCCEEDED -- FINAL SQL")
            print(sql_query)
        else:
            fallback_sql = generate_fallback_query(product_name, indicator, filters_meta)
            print_section("ALL RETRIES FAILED -- USING FALLBACK SQL")
            print(fallback_sql)

            result, db_error = execute_query(product_name, fallback_sql)
            all_sql_history.append({"type": "fallback", "sql": fallback_sql})
            if db_error:
                print(f"\n[FALLBACK DB ERROR] {db_error}")
                all_error_history.append({"type": "fallback", "error": db_error})
            sql_query = fallback_sql
    else:
        print(f"\n[DB] Query executed successfully. Rows returned: {len(result)}")

    log_performance({
        "timestamp":                time.strftime("%Y-%m-%d %H:%M:%S"),
        "user_query":               user_query,
        "product":                  product_name,
        "indicator":                indicator,
        "aggregation":              is_agg,
        "prompt_folder_used":       used_folder,
        "prompt_file_used":         prompt_file,
        "relevant_columns":         list(analysis["filters"].keys()),
        "distinct_relevant_values": analysis["filters"],
        "non_relevant_columns":     analysis["non_rel_column"],
        "all_generated_sql":        all_sql_history,
        "all_errors":               all_error_history,
        "final_sql_used":           sql_query,
        "final_error":              db_error
    })

    if db_error:
        return {"success": False, "error": db_error}

    columns = list(result[0].keys()) if result else []
    rows    = [list(row.values()) for row in result]

    print_section("PROCESS COMPLETE")
    print(f"  Rows Returned : {len(rows)}")
    print(f"  Final SQL     : {sql_query[:120]}...")

    return {
        "success":        True,
        "dataset":        product_name,
        "indicator":      indicator,
        "indicator_code": indicator.lower().replace(" ", "_"),
        "sql":            sql_query,
        "columns":        columns,
        "rows":           rows,
        "row_count":      len(rows),
        "filters_meta":   filters_meta
    }


# =========================
# MAIN (CLI mode)
# =========================
if __name__ == "__main__":
    metadata = load_json("metadata.json")

    while True:
        product    = input("\nEnter product name: ")
        user_query = input("Enter your query: ")

        result = process_query(user_query, product)
        print("\nFINAL OUTPUT:")
        print(json.dumps({
            "indicator": result.get("indicator"),
            "sql":       result.get("sql"),
            "error":     result.get("error")
        }, indent=4))