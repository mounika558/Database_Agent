"""MySQL helpers: connection, schema description, and guarded query execution."""
import os
import re
from decimal import Decimal

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

MAX_ROWS = 100

# Words that must never appear in a generated query (checked outside string literals).
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|rename|"
    r"call|execute|handler|outfile|dumpfile|load_file|sleep|benchmark)\b|"
    r"replace\s+into|for\s+update|lock\s+in\s+share",
    re.IGNORECASE,
)


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "ecommerce"),
    )


def get_schema() -> str:
    """Return a compact text description of all tables, columns and foreign keys."""
    db_name = os.getenv("DB_NAME", "ecommerce")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, COLUMN_KEY
               FROM INFORMATION_SCHEMA.COLUMNS
               WHERE TABLE_SCHEMA = %s
               ORDER BY TABLE_NAME, ORDINAL_POSITION""",
            (db_name,),
        )
        tables: dict[str, list[str]] = {}
        for table, col, ctype, key in cur.fetchall():
            tag = " PK" if key == "PRI" else ""
            tables.setdefault(table, []).append(f"{col} {ctype}{tag}")

        cur.execute(
            """SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
               FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
               WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL""",
            (db_name,),
        )
        fks = [f"{t}.{c} -> {rt}.{rc}" for t, c, rt, rc in cur.fetchall()]
    finally:
        conn.close()

    lines = [f"Table {t}({', '.join(cols)})" for t, cols in tables.items()]
    if fks:
        lines.append("Foreign keys: " + "; ".join(fks))
    return "\n".join(lines)


def validate_sql(sql: str) -> str:
    """Return a cleaned, safe SELECT statement or raise ValueError."""
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise ValueError("Empty query.")

    # Blank out string literals so keywords inside values don't trigger checks.
    no_strings = re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", "''", sql)

    if "/*" in no_strings or "--" in no_strings or "#" in no_strings:
        raise ValueError("SQL comments are not allowed.")
    if ";" in no_strings:
        raise ValueError("Only a single statement is allowed.")
    if not re.match(r"^\s*(select|with)\b", no_strings, re.IGNORECASE):
        raise ValueError("Only SELECT queries are allowed.")
    if FORBIDDEN.search(no_strings):
        raise ValueError("Query contains a forbidden keyword.")

    if not re.search(r"\blimit\b", no_strings, re.IGNORECASE):
        sql += f" LIMIT {MAX_ROWS}"
    return sql


def run_query(sql: str):
    """Validate and execute a SELECT. Returns (columns, rows_as_dicts, final_sql)."""
    sql = validate_sql(sql)
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        # Extra safety layers on top of the read-only DB user.
        cur.execute("SET SESSION TRANSACTION READ ONLY")
        try:
            cur.execute("SET SESSION MAX_EXECUTION_TIME = 10000")  # 10 s
        except mysql.connector.Error:
            pass
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
    finally:
        conn.close()

    clean = [
        {k: (float(v) if isinstance(v, Decimal) else v) for k, v in row.items()}
        for row in rows
    ]
    return columns, clean, sql