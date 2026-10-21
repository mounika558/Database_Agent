"""MCP SERVER: exposes the e-commerce MySQL database as tools.

You normally don't run this file yourself. The MCP client (mcp_agent.py)
starts it automatically as a subprocess and talks to it over stdio.

Optional manual test (needs: pip install "mcp[cli]"):
    mcp dev mcp_server.py

IMPORTANT: never use print() in this file. In stdio mode, stdout is the
channel used for the MCP protocol, and stray prints would corrupt it.
"""
import json

from mcp.server.fastmcp import FastMCP

import db

mcp = FastMCP("ecommerce-db")


@mcp.tool()
def get_schema() -> str:
    """Return all tables, columns and foreign keys of the e-commerce database.
    Call this first, before writing any SQL."""
    return db.get_schema()


@mcp.tool()
def run_sql_query(sql: str) -> str:
    """Run ONE read-only MySQL SELECT query and return the rows as JSON.
    Only SELECT is allowed. If the query fails, an 'error' field explains why,
    so you can fix the query and try again."""
    try:
        columns, rows, final_sql = db.run_query(sql)
        return json.dumps(
            {"columns": columns, "rows": rows, "sql": final_sql}, default=str
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)})


if __name__ == "__main__":
    mcp.run(transport="stdio")