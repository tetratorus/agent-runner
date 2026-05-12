# twak — Trust Wallet Agent Kit CLI

AI-agent-focused CLI for Trust Wallet, exposing on-chain actions (swap,
transfer, DCA, limit orders) across 25+ chains.

## Install

```bash
npm install -g @trustwallet/cli
# or run ad-hoc:
npx @trustwallet/cli --version
```

Source: [developer.trustwallet.com — Agent SDK](https://developer.trustwallet.com/developer/agent-sdk).

## Authenticate

1. Create an API key (`access_id` + HMAC secret) at
   [portal.trustwallet.com](https://portal.trustwallet.com).
2. Initialize the CLI:
   ```bash
   twak init --api-key <access_id> --api-secret <hmac_secret>
   ```

Credentials persist to **`~/.twak/credentials.json`** (mode `0600`).

## Env vars

For ephemeral environments only (CI/CD), the CLI also accepts:
- `TWAK_ACCESS_ID`
- `TWAK_HMAC_SECRET`

The official docs explicitly warn against putting these in shell rc files
— use them for runtime injection only.

## Sources

- [Trust Wallet Agent SDK overview](https://developer.trustwallet.com/developer/agent-sdk)
- [Authentication](https://developer.trustwallet.com/developer/agent-sdk/authentication)
- [npm: @trustwallet/cli](https://www.npmjs.com/package/@trustwallet/cli)
- [Announcement post](https://trustwallet.com/blog/announcements/introducing-the-trust-wallet-agent-kit-twak-your-ai-agent-can-now-act-on-crypto)
