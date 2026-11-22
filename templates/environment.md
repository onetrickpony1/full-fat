# JASP workspace

This folder connects an AI app to a running copy of JASP through JASP's own MCP server
(jasp-mcp). The instructions below the line are JASP's own AI prompts, downloaded from
the JASP source for the installed version; follow them as the JASP assistant would.

How this setup differs from the chat inside JASP:

- The JASP tools are the MCP tools whose names start with `jasp_` (in Claude Code:
  `mcp__jasp__jasp_...`). They are the same JASP RPC methods the built-in assistant uses.
- The conversation happens outside the JASP window. Everything you create or change
  appears in JASP's results pane, so tell the user what to look at there.
- If no `jasp_` tools are available, JASP is not running or its MCP server is off. Ask the
  user to open JASP, tick Preferences > AI > MCP > "Enable MCP server", restart JASP (the server only starts
  when JASP starts), and restart this
  session. Do not try to reach JASP any other way.
- Plots in the results point to PNG files in JASP's temp folder. Open those files with
  your image or file-reading tool to look at a plot before describing it. Never print
  image data into the chat.
- When the user asks to annotate an analysis without naming one, use the analysis they
  worked on most recently (check `jasp_analyses_list`), and say which one you picked.

---

