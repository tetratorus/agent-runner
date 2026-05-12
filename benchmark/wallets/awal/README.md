# awal — Coinbase Agentic Wallet CLI

`awal`. Tagline: *"Coinbase Wallet CLI for payments and crypto"*. MPC-secured
agent wallet on Base; per-tx limits, session caps, gasless settlement,
x402 payments. Distributed via Coinbase's Skills package.

## Install

```bash
# Non-interactive — installs every skill from the bundle, globally:
npx skills add coinbase/agentic-wallet-skills --all -g

# The bundle contains 9 skills and pins the `awal` CLI version. After
# install, `npx awal …` works directly.
```

The bare `npx skills add coinbase/agentic-wallet-skills` is interactive
(prompts to pick skills + target agent). Use `--all -g` for unattended.

## Authenticate

Two-step email-OTP:

```bash
npx awal auth login user@example.com
# email arrives with a 6-digit OTP
npx awal auth verify <otp>
```

Session persistence is configurable:

```bash
npx awal persistence enable     # keep wallet window open after disconnect
npx awal persistence disable
npx awal persistence status
```

Storage path isn't documented; `npx awal status` will report it at runtime.

## Surface relevant to the benchmark

```
status       wallet server health + auth status
balance      across all chains, or --chain <chain>
address      EVM + Solana
send         <amount> <recipient>
trade|swap   <amount> <from> <to>     (CDP Swap API)
x402         x402 payment protocol commands
auth         login <email> | verify <otp>
persistence  enable | disable | status
show         show + focus wallet companion window
quit         quit the wallet application
telemetry    analytics + health check metrics
```

## Sources

- [docs.cdp.coinbase.com — agentic-wallet/cli/quickstart](https://docs.cdp.coinbase.com/agentic-wallet/cli/quickstart)
- [github.com/coinbase/agentic-wallet-skills](https://github.com/coinbase/agentic-wallet-skills)
- `npx awal --help`, `npx awal auth --help`, `npx awal persistence --help`
  (probed inside `node:20` container)
