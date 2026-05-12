# coinfello — CoinFello agent CLI

`@coinfello/agent-cli v0.3.6`. Tagline: *"CoinFello CLI - Smart Account
interactions"*. ERC-4337 smart account + ERC-7710 fine-grained delegation
model via MetaMask Smart Accounts Kit — the user's signing key stays
local; the agent acts under a scoped delegation.

## Install

```bash
npm install -g @coinfello/agent-cli
# binary lands at: coinfello
# Requires Node.js ≥ 20.
```

## Authenticate / set up

```bash
# 1. Create the smart account (writes its address to local config).
coinfello create_account
coinfello get_account            # verify

# 2. Sign in to a server using SIWE with that account.
coinfello sign_in
```

After sign-in you grant CoinFello delegations:

```bash
coinfello send_prompt "<task description>"     # the server may request a delegation
coinfello approve_delegation_request           # sign + submit it
coinfello set_delegation <signed-JSON>         # or import an existing one
```

For higher-security signing, the package ships a Secure Enclave daemon:

```bash
coinfello signer-daemon
```

Conversation state:

```bash
coinfello new_chat                # clear saved chat ID, start fresh
```

The "local config" mentioned in the help text is the persistence target —
exact path isn't surfaced in `--help`; check `~/.coinfello/` or similar
at runtime.

## Full command list

```
create_account             Create a smart account, save address to local config
get_account                Print current smart account address
sign_in                    SIWE sign-in
set_delegation <json>      Store a signed delegation in local config
new_chat                   Clear saved chat ID, start fresh
send_prompt <prompt>       Send a prompt to CoinFello server
approve_delegation_request Approve + sign a pending delegation, submit
signer-daemon              Manage the Secure Enclave signing daemon
```

## Sources

- [npm: @coinfello/agent-cli](https://www.npmjs.com/package/@coinfello/agent-cli)
- [GitHub: CoinFello/agent-cli](https://github.com/CoinFello/agent-cli)
- `coinfello --help` (probed inside `node:20` container)
- [MetaMask Smart Accounts Kit](https://metamask.io/developer/delegation-toolkit) — the underlying delegation framework
