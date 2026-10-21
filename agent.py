"""LangGraph text-to-SQL agent powered by Gemini.

Flow:
    START -> generate_sql -> execute_sql -> answer -> END
                  ^              |
                  +-- (on error, up to MAX_ATTEMPTS) --+
"""
import json
import os
import re
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph

import db

load_dotenv()

MAX_ATTEMPTS = 3
NO_SQL = "NO_SQL"


class AgentState(TypedDict, total=False):
    question: str
    history: str
    schema: str
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    error: str | None
    attempts: int
    answer: str


def _llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash"),
        temperature=0.5,
    )


def _text(msg) -> str:
    """Gemini may return a string or a list of content blocks."""
    content = msg.content
    if isinstance(content, str):
        return content
    return "".join(p if isinstance(p, str) else p.get("text", "") for p in content)


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:sql)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


SQL_SYSTEM = """You are an expert MySQL analyst for an e-commerce company.
Convert the user's question into ONE MySQL SELECT query.

Database schema:
{schema}

Rules:
- Use only the tables and columns in the schema. Never invent columns.
- Output ONLY the raw SQL. No explanations, no markdown, no backticks, no semicolon.
- Read-only: never write INSERT/UPDATE/DELETE/DDL.
- Monetary values are in Indian Rupees (INR).
- For revenue/sales, exclude orders with status 'cancelled' unless asked otherwise.
- Use CURDATE() / NOW() for relative dates like "this month" or "last 30 days".
- Prefer readable column aliases (e.g. total_revenue, customer_name).
- If the question cannot be answered from this database, output exactly: {no_sql}
"""


# ---------- nodes ----------

def generate_sql(state: AgentState) -> AgentState:
    attempts = state.get("attempts", 0) + 1

    user_parts = []
    if state.get("history"):
        user_parts.append(f"Conversation so far:\n{state['history']}\n")
    user_parts.append(f"Question: {state['question']}")
    if state.get("error"):
        user_parts.append(
            f"\nYour previous query:\n{state.get('sql', '')}\n"
            f"failed with this error:\n{state['error']}\n"
            "Write a corrected query."
        )

    response = _llm().invoke(
        [
            SystemMessage(content=SQL_SYSTEM.format(schema=state["schema"], no_sql=NO_SQL)),
            HumanMessage(content="\n".join(user_parts)),
        ]
    )
    return {"sql": _strip_fences(_text(response)), "attempts": attempts}


def execute_sql(state: AgentState) -> AgentState:
    try:
        columns, rows, final_sql = db.run_query(state["sql"])
        return {"columns": columns, "rows": rows, "sql": final_sql, "error": None}
    except Exception as exc:  # validation or MySQL error -> feed back to the LLM
        return {"error": str(exc), "rows": [], "columns": []}


ANSWER_SYSTEM = """You are a helpful data assistant for an e-commerce company.
Answer the user's question in clear, friendly natural language using ONLY the
query result provided. Be concise. Format money as INR (e.g. ₹1,299.00).
If the result is a list, summarise it and show the key items. If the result is
empty, say no matching data was found."""


def answer(state: AgentState) -> AgentState:
    if state.get("sql") == NO_SQL:
        return {
            "answer": "I can only answer questions about this store's data: customers, "
                      "products, orders, payments and reviews. Could you rephrase?",
            "rows": [],
            "sql": "",
        }
    if state.get("error"):
        return {
            "answer": "Sorry, I couldn't get a valid result for that question after "
                      f"{state.get('attempts', 0)} attempts. Try rephrasing it.",
        }

    rows_json = json.dumps(state.get("rows", [])[:50], default=str)
    response = _llm().invoke(
        [
            SystemMessage(content=ANSWER_SYSTEM),
            HumanMessage(
                content=f"Question: {state['question']}\n\nSQL used:\n{state['sql']}\n\n"
                        f"Result rows (JSON):\n{rows_json}"
            ),
        ]
    )
    return {"answer": _text(response).strip()}


# ---------- routing ----------

def after_generate(state: AgentState) -> str:
    return "answer" if state["sql"] == NO_SQL else "execute_sql"


def after_execute(state: AgentState) -> str:
    if state.get("error") and state.get("attempts", 0) < MAX_ATTEMPTS:
        return "generate_sql"
    return "answer"


# ---------- graph ----------

def build_graph():
    g = StateGraph(AgentState)
    g.add_node("generate_sql", generate_sql)
    g.add_node("execute_sql", execute_sql)
    g.add_node("answer", answer)

    g.add_edge(START, "generate_sql")
    g.add_conditional_edges(
        "generate_sql", after_generate, {"answer": "answer", "execute_sql": "execute_sql"}
    )
    g.add_conditional_edges(
        "execute_sql", after_execute, {"generate_sql": "generate_sql", "answer": "answer"}
    )
    g.add_edge("answer", END)
    return g.compile()


def ask(graph, schema: str, question: str, history: str = "") -> AgentState:
    """Run one question through the graph and return the final state."""
    return graph.invoke(
        {
            "question": question,
            "history": history,
            "schema": schema,
            "sql": "",
            "error": None,
            "attempts": 0,
        }
    )


if __name__ == "__main__":
    # Quick CLI test: python agent.py
    graph = build_graph()
    schema = db.get_schema()
    while True:
        q = input("\nAsk (or 'exit'): ").strip()
        if q.lower() in {"exit", "quit", ""}:
            break
        result = ask(graph, schema, q)
        print("\nSQL:", result.get("sql"))
        print("Answer:", result.get("answer"))