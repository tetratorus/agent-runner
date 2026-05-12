# phantom-mcp — Phantom MCP server

`@phantom/mcp-server v1.2.7`. MCP server that exposes Phantom wallet
operations (sign messages, send transactions, transfer tokens, swap,
get addresses) to MCP-speaking agents. Solana + EVM. Repo:
[github.com/phantom/phantom-connect-sdk](https://github.com/phantom/phantom-connect-sdk).

## Install (for Claude Code)

```bash
claude mcp add phantom -- npx -y @phantom/mcp-server@latest

# Verify:
claude mcp list
```

For other MCP-capable clients (Cursor, Claude Desktop, etc.) register the
same package via that client's MCP-server config.

You can also install the binary globally if you want to run it stand-alone:

```bash
npm install -g @phantom/mcp-server
phantom-mcp            # starts the server (stdio transport)
```

The package's bin entry is `phantom-mcp → ./dist/bin.js`. It depends on
`@phantom/cli ^1.2.7`.

## Authenticate

> On first use, a browser window opens for device-code sign-in.

So: the first time an agent calls a Phantom tool through the MCP server,
the server pops a browser at `connect.phantom.app`, you sign in with
Google or Apple, and the session is bound to this machine.

Session storage path isn't in the official docs — press coverage cites
`~/.phantom-mcp/session.json` (`0600`); confirm at runtime before
relying on it.

## Caveats for the benchmark

- Only agents that speak MCP can use phantom-mcp. In our matrix only
  `claude-code` qualifies — non-MCP agents should be skipped for this
  wallet.
- The OAuth session has to be completed manually once on the host
  before any test can run. There is no headless auth flow.
- `phantom-mcp` advertises its own tool list to the agent at MCP
  handshake — the benchmark sees those tools in proxy logs as
  `tool_use` blocks just like any other.

## Sources

- [docs.phantom.com — Phantom MCP server](https://docs.phantom.com/phantom-mcp-server)
- [Get started with Phantom MCP](https://help.phantom.com/hc/en-us/articles/49235725504147-Get-started-with-Phantom-MCP)
- [npm: @phantom/mcp-server](https://www.npmjs.com/package/@phantom/mcp-server)
- Package metadata inspected in `node:20` container
