# coinfello — CoinFello agent CLI

CoinFello drives any EVM smart contract via an AI agent. Security model
is ERC-4337 smart accounts + ERC-7710 fine-grained delegations through
the MetaMask Smart Accounts Kit — the user's signing key never leaves
their device; the agent acts under a scoped delegation.

## Install

```bash
# Requires Node.js 20+. npx ships with node, no separate install needed.
npx @coinfello/agent-cli <command>
```

The CLI was also published as an OpenClaw skill ("brettcleary/coinfello")
for agents that consume skills, but the canonical entry point is the
`@coinfello/agent-cli` npm package.

## Authenticate

Sign in with Ethereum (SIWE) using the CLI's `signin` command. This
produces a session tied to the smart account. From the announcement:

> Interact with CoinFello using the @coinfello/agent-cli to create a smart
> account, sign in with SIWE, manage delegations, send prompts with
> server-driven ERC-20 token subdelegations, and check transaction status.

Concrete CLI subcommands and persisted paths aren't documented in the
public announcements I could find. The SKILL.md at
`openclaw/skills/skills/brettcleary/coinfello/SKILL.md` is referenced
but currently 404s on GitHub — needs to be confirmed live.

## Env vars

None documented in the public material.

## Sources

- [CoinFello launch — open source AI agent transactions to MetaMask Smart Accounts](https://www.opensourceforu.com/2026/03/coinfello-brings-open-source-ai-agent-transactions-to-metamask-smart-accounts/)
- [DL News — CoinFello launches OpenClaw skill](https://www.dlnews.com/external/coinfello-launches-openclaw-skill-for-ai-agent-transactions/)
- [Tech Startups — CoinFello: First self-sovereign AI agent](https://techstartups.com/2025/11/17/coinfello-the-first-self-sovereign-ai-agent-for-using-and-automating-any-smart-contract/)
- [MetaMask Smart Accounts Kit](https://metamask.io/developer/delegation-toolkit) (the underlying delegation framework)

## Gaps to verify before benchmarking

- Exact subcommands of `@coinfello/agent-cli` (signin, delegate, …).
- Where the smart-account address + delegation state are stored.
- Whether a developer key from a CoinFello portal is required, or sign-in
  alone is sufficient.
