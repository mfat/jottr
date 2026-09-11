# Agent instructions for this repo

Before doing substantial work, use Codebase Memory MCP (`codebase-memory-mcp`) for:
- project architecture (`get_architecture`)
- finding symbols and relationships (`search_graph`, `trace_path`)
- code lookup (`get_code_snippet`, `search_code`)
- graph queries (`query_graph`, `get_graph_schema`)

Project name in the graph: `jottr`

Do not rely only on the graph. After retrieving Codebase Memory context, verify it against the current repository files.

For implementation tasks:
1. Query Codebase Memory for relevant context.
2. Inspect the current code.
3. Explain the plan briefly.
4. Make minimal changes.
5. Run relevant tests or explain why they were not run.

To refresh the index after large changes:
`index_repository` with `repo_path` `/home/mahdi/GitHub/jottr`, `name` `jottr`, and preferred `mode` (`full` / `moderate` / `fast`).
Set `persistence: true` to update `.codebase-memory/graph.db.zst` for teammates.
