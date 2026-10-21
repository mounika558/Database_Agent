"""MCP CLIENT + LangGraph tool-calling agent.

Flow:
    START -> agent (Gemini decides) --tool call?--> tools (MCP client -> MCP server -> MySQL)
                ^                                        |
                +----------------------------------------+
    When Gemini makes no more tool calls, the graph ends with the final answer.

Run a quick test:  python mcp_agent.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent import _llm, _text  # reuse the Gemini helpers from agent.py

load_dotenv()

SERVER_PATH = str(Path(__file__).with_name("mcp_server.py"))

SYSTEM_PROMPT = """You are a helpful data assistant for an e-commerce company.
You can answer questions ONLY by using your tools:
1. Call get_schema first (once) to see the tables and columns.
2. Call run_sql_query with ONE MySQL SELECT query to get the data.
3. If run_sql_query returns an error, fix the query and try again.
4. Then answer in clear, friendly language using only the returned rows.

Rules:
- Never invent tables or columns. Never write INSERT/UPDATE/DELETE.
- Money is in Indian Rupees; format it like ₹1,299.00.
- For revenue/sales, exclude orders with status 'cancelled' unless asked.
- If the question has nothing to do with this database, say so politely
  without calling any tool."""


def _client() -> MultiServerMCPClient:
    # The client starts mcp_server.py as a subprocess and talks to it via stdio.
    return MultiServerMCPClient(
        {
            "ecommerce_db": {
                "transport": "stdio",
                "command": sys.executable,  # same Python (your venv) as this app
                "args": [SERVER_PATH],
            }
        }
    )


def _payload(msg: ToolMessage) -> dict:
    """Parse the JSON text returned by our run_sql_query tool."""
    content = msg.content
    if isinstance(content, list):
        content = "".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in content
        )
    try:
        return json.loads(content)
    except Exception:
        return {}


async def _run(question: str, history: str = "") -> dict:
    client = _client()
    tools = await client.get_tools()  # discovers tools from the MCP server
    llm = _llm().bind_tools(tools)

    async def call_model(state: MessagesState):
        return {"messages": [await llm.ainvoke(state["messages"])]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)  # -> "tools" or END
    graph.add_edge("tools", "agent")
    app = graph.compile()

    user_text = question
    if history:
        user_text = f"Conversation so far:\n{history}\n\nNew question: {question}"

    result = await app.ainvoke(
        {"messages": [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_text)]},
        {"recursion_limit": 14},
    )

    # Collect the last SQL query, its rows, and the final answer for the UI.
    sql, rows = "", []
    for m in result["messages"]:
        if isinstance(m, AIMessage):
            for call in m.tool_calls or []:
                if call["name"] == "run_sql_query":
                    sql = call["args"].get("sql", sql)
        elif isinstance(m, ToolMessage) and m.name == "run_sql_query":
            data = _payload(m)
            if "rows" in data:
                rows = data["rows"]
                sql = data.get("sql", sql)

    final = next(
        (m for m in reversed(result["messages"]) if isinstance(m, AIMessage) and not m.tool_calls),
        None,
    )
    return {"answer": _text(final).strip() if final else "No answer.", "sql": sql, "rows": rows}


def ask_mcp(question: str, history: str = "") -> dict:
    """Sync wrapper so Streamlit (which is synchronous) can call the async agent."""
    return asyncio.run(_run(question, history))


if __name__ == "__main__":
    while True:
        q = input("\nAsk (or 'exit'): ").strip()
        if q.lower() in {"exit", "quit", ""}:
            break
        out = ask_mcp(q)
        print("\nSQL:", out["sql"])
        print("Answer:", out["answer"])