# phantom-mcp — Phantom MCP server

MCP server that exposes Phantom wallet operations (sign messages,
send transactions, transfer tokens, swap, get addresses) to any
MCP-speaking agent. Solana + EVM.

## Install (for Claude Code)

```bash
claude mcp add phantom -- npx -y @phantom/mcp-server@latest
```

Verify:
```bash
claude mcp list
```

The npm package is **`@phantom/mcp-server`**.

For other MCP-capable clients (Cursor, Claude Desktop, etc.) the same
package is registered through that client's MCP-server config UI or file.

## Authenticate

Quote from the docs:

> On first use, a browser window opens for device-code sign-in.

So: the first time the agent calls a phantom tool, the MCP server pops
a browser, you complete OAuth (Google/Apple) at `connect.phantom.app`,
and the session is bound to this machine.

## Persistence

Not documented in the page I read. Earlier press coverage mentions
`~/.phantom-mcp/session.json` with `0600` perms — verify this against
the running server before relying on it for the benchmark.

## Env vars

None documented.

## Sources

- [docs.phantom.com — MCP server](https://docs.phantom.com/phantom-mcp-server)
- [Get started with Phantom MCP](https://help.phantom.com/hc/en-us/articles/49235725504147-Get-started-with-Phantom-MCP)
- [npm: @phantom/mcp-server](https://www.npmjs.com/package/@phantom/mcp-server)
- [docs.phantom.com — Phantom Connect SDK MCP server](https://docs.phantom.com/resources/mcp-server) (different MCP server, for docs access; do not confuse the two)

## Caveats for the benchmark

- Only agents that speak MCP can use phantom-mcp (currently `claude-code`
  in our matrix). Skip non-MCP agents for this wallet.
- The OAuth session has to be completed manually once per host before
  any tests can run. There's no headless flow described.
