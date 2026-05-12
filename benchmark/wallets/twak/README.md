# twak — Trust Wallet Agent Kit CLI

`twak v0.11.0`. Tagline: *"Trust Wallet Agent — AI-powered multichain wallet SDK"*.

## Install

```bash
npm install -g @trustwallet/cli
# binary lands at: twak
```

## Authenticate

Get an API key (`access_id` + HMAC secret) from
[portal.trustwallet.com](https://portal.trustwallet.com), then either:

```bash
# Persistent on this machine (recommended for local benchmarking)
twak init --api-key <access_id> --api-secret <hmac_secret> [--wc-project-id <id>]
# Or check / re-do later:
twak auth setup
twak auth status
```

For ephemeral/CI use, set instead:
- `TWAK_ACCESS_ID`
- `TWAK_HMAC_SECRET`

Per the docs, these env vars are intended for runtime injection only —
don't put them in `~/.zshrc`/`~/.bashrc`. Credentials from `twak init`
persist to `~/.twak/credentials.json` with `0600` perms.

## Surface relevant to the benchmark

```
init        Initialize twak configuration
auth        setup | status — manage authentication
wallet      Manage agent wallet
transfer    Transfer tokens to an address
swap        Quote or execute a token swap
erc20       ERC-20 token operations
balance     Get token balance for an address (native or ERC-20)
history     Get transaction history (single chain or all chains)
tx          Get transaction details by hash
chains      List supported chains
validate    Validate an address
risk        Check token risk and security info
asset       Get asset info
search      Search for tokens
trending    Get trending tokens
price       Get token price
serve       Start MCP server (stdio) or REST API for AI agents
automate    Manage DCA and limit order automations
onramp      Buy or sell crypto with fiat
x402        x402 micropayment protocol
alert       Manage price alerts
telemetry   off by default
```

Note `twak serve` exposes the same surface as an MCP server — useful for
MCP-capable agents that want to call twak as a tool server instead of
shelling out.

## Sources

- [Trust Wallet Agent SDK overview](https://developer.trustwallet.com/developer/agent-sdk)
- [Authentication](https://developer.trustwallet.com/developer/agent-sdk/authentication)
- [npm: @trustwallet/cli](https://www.npmjs.com/package/@trustwallet/cli)
- `twak --help`, `twak init --help`, `twak auth --help` (probed inside `node:20` container)
