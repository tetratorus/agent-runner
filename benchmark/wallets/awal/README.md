# awal — Coinbase Agentic Wallet CLI

Coinbase Developer Platform's CLI for provisioning + driving an
MPC-secured agent wallet on Base. Per-transaction limits, session caps,
gasless settlement, x402 payments.

## Install

`awal` is installed as a dependency of Coinbase's skills package:

```bash
npx skills add coinbase/agentic-wallet-skills
```

After that, the `awal` CLI is callable via `npx awal …`. Direct `npm install awal`
is not the documented path — the skills package pins the supported `awal` version.

## Authenticate

Two-step email-OTP flow:

```bash
npx awal auth login user@example.com
# email arrives with a flowId + 6-digit code
npx awal auth verify <flowId> <otp>
```

Sessions can persist between runs:

```bash
npx awal persistence enable
npx awal persistence disable
```

## Env vars

None documented.

## Persistence

The docs don't say where session state lives on disk. The `persistence
enable/disable` commands imply there's a config file managed by the CLI;
exact path needs to be checked at runtime (probably `~/.awal/` or
similar — confirm before scripting against it).

## Sources

- [docs.cdp.coinbase.com — agentic-wallet/cli/quickstart](https://docs.cdp.coinbase.com/agentic-wallet/cli/quickstart)
- [github.com/coinbase/agentic-wallet-skills](https://github.com/coinbase/agentic-wallet-skills)
- [Coinbase agentic wallets launch post](https://www.coinbase.com/developer-platform/discover/launches/agentic-wallets)
