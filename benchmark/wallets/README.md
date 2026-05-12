# Wallet Workspace Setup

Each wallet has an ignored `workspace/` directory. Prepare it once, then
`benchmark/run.py` copies it into each `(wallet, agent, test)` cell. The copied
workspace must contain everything the wallet CLI needs to run without package
installation during the test: `node_modules`, CLI config, auth/session state,
and any `.env` values.

Always prepare workspaces inside Docker with `--platform linux/amd64`, matching
`agent-run`. Do not install Node packages on macOS and copy them into the
benchmark; native optional dependencies such as `@napi-rs/keyring` will be for
the wrong platform.

Go into the wallet folder you are preparing and run its local setup script:

```bash
cd benchmark/wallets/twak && ./setup.sh
cd benchmark/wallets/awal && ./setup.sh
cd benchmark/wallets/baw && ./setup.sh
cd benchmark/wallets/coinfello && ./setup.sh
cd benchmark/wallets/phantom-mcp && ./setup.sh
```

Each script owns that wallet's real setup flow. `twak/setup.sh`, for example,
installs the CLI, prompts for API credentials if they are missing, creates the
agent wallet if needed, and writes `.env` with `TWAK_WALLET_PASSWORD`.

## Runtime Adapter

`agent-run` mounts the copied cell workspace at `/workspace`, loads
`/workspace/.env` when present, and sources `docker/wallet-bootstrap.sh` before
starting the agent. The bootstrap:

- prepends `/workspace/node_modules/.bin` to `PATH`;
- symlinks wallet state directories such as `.twak`, `.phantom-mcp`,
  `.clawdbot`, `.agents`, and `.cache` into the agent user's home;
- leaves the agent's own home config intact.

This lets agents call `twak`, `awal`, `baw`, `coinfello`, or `phantom` directly
while the wallet state still comes from the copied workspace.

## Wallet Notes

Four wallets keep their auth in a file-based session that's portable across
container restarts — set them up once, every test cell reuses a copy of the
workspace. **awal** is the exception: its session lives in an Electron
renderer's RAM and won't survive a container exit, so the in-container `awal`
is a thin shim that forwards argv to the host's authenticated `awal` CLI.

- `twak`: install `@trustwallet/cli@0.11.0` in Docker. Auth state lives in
  `.twak/`; wallet decryption needs `TWAK_WALLET_PASSWORD` from `.env`.
- `awal`: **host-shim**. Install and authenticate `awal` on the macOS host
  (`npm i -g awal && awal auth login <email>`). `setup.sh` only writes a
  Python shim to `workspace/node_modules/.bin/awal`; the shim forwards argv
  to `host-awal-proxy.py` over TCP on port 7788. `benchmark/run.py`
  auto-starts the proxy when awal is in the wallets list and tears it down
  on exit — no separate process to babysit. All tests share the same host
  wallet (fine for read-only; transaction tests mutate real state).
- `baw`: install `@binance/agentic-wallet@1.0.9` and the
  `binance-agentic-wallet` skill via `npx skills add ...`. Auth:
  `baw auth signin --json` then `baw auth verify --qrCodeId <id> --json`.
  Session is encrypted with `BINANCE_INSTANCE_ID` and persisted to
  `.baw/session.json`.
- `coinfello`: install `@coinfello/agent-cli@0.3.6`. `coinfello create_account`
  writes the private key + smart-account address to
  `.clawdbot/skills/coinfello/config.json`; `coinfello sign_in` appends a
  `session_token` to the same file. `sign_in` calls
  `smartAccount.signMessage`, which requires a working Ethereum mainnet RPC
  — viem's default rate-limits/hangs. `setup.sh` resolves the RPC from
  `$RPC_URL_OVERRIDE`, then `$INFURA_API_KEY`, then a public fallback.
- `phantom-mcp`: install `@phantom/mcp-server@1.2.7`. Auth is a device-code
  OAuth flow (`phantom login --display-mode text`); the resulting
  `.phantom-mcp/session.json` is portable. The MCP server itself runs
  in-container per test (registered via `.mcp.json` for Claude Code's MCP
  client), so only `claude-code` can drive this wallet.
