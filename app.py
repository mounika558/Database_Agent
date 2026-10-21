"""Streamlit chat UI.  Run:  streamlit run app.py"""
import pandas as pd
import streamlit as st

import db
from agent import ask, build_graph

try:
    from mcp_agent import ask_mcp
    MCP_OK = True
except ImportError:  # mcp libraries not installed yet
    MCP_OK = False

st.set_page_config(page_title="E-commerce Data Assistant", page_icon="🛒", layout="wide")
st.title("🛒 E-commerce Data Assistant")
st.caption("Ask questions about your store in plain English. Powered by Gemini + LangGraph.")


@st.cache_resource
def get_graph():
    return build_graph()


@st.cache_resource
def get_schema():
    return db.get_schema()


try:
    graph = get_graph()
    schema = get_schema()
except Exception as exc:
    st.error(f"Could not start the agent: {exc}")
    st.info("Check your .env file (API key, DB credentials) and that MySQL is running.")
    st.stop()

EXAMPLES = [
    "Who are the top 3 customers by total spend?",
    "What is the total revenue by category?",
    "Which products have an average rating below 4?",
    "How many orders are in each status?",
    "Which city has the most customers?",
    "Which products are low on stock (under 50)?",
]

# ---------- sidebar ----------
MODES = ["Workflow (direct DB)", "MCP (tool calling)"]
with st.sidebar:
    mode = st.radio("Agent mode", MODES, index=0)
    if mode == MODES[1] and not MCP_OK:
        st.warning("Run: pip install mcp langchain-mcp-adapters")
        mode = MODES[0]
    st.divider()
    st.header("Try these")
    for q in EXAMPLES:
        if st.button(q, use_container_width=True):
            st.session_state["pending"] = q
    st.divider()
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()
    with st.expander("Database schema"):
        st.code(schema, language="text")

# ---------- chat state ----------
if "messages" not in st.session_state:
    st.session_state["messages"] = []


def render(msg: dict):
    st.markdown(msg["content"])
    if msg.get("sql"):
        with st.expander("SQL query"):
            st.code(msg["sql"], language="sql")
    if msg.get("rows"):
        st.dataframe(pd.DataFrame(msg["rows"]), use_container_width=True)


def build_history(messages: list[dict], max_msgs: int = 6) -> str:
    lines = []
    for m in messages[-max_msgs:]:
        if m["role"] == "user":
            lines.append(f"User: {m['content']}")
        else:
            sql = f" (SQL used: {m['sql']})" if m.get("sql") else ""
            lines.append(f"Assistant: {m['content']}{sql}")
    return "\n".join(lines)


for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        render(m)

# ---------- input ----------
prompt = st.chat_input("Ask about customers, products, orders...") or st.session_state.pop(
    "pending", None
)

if prompt:
    history = build_history(st.session_state["messages"])
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                if mode == MODES[1]:
                    result = ask_mcp(prompt, history)
                else:
                    result = ask(graph, schema, prompt, history)
                reply = {
                    "role": "assistant",
                    "content": result.get("answer", "No answer."),
                    "sql": result.get("sql", ""),
                    "rows": result.get("rows", []),
                }
            except Exception as exc:
                reply = {"role": "assistant", "content": f"Something went wrong: {exc}"}
        render(reply)
    st.session_state["messages"].append(reply)