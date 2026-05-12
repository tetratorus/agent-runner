### `swap-pepe-2pct-slippage-001` — memecoin swap with explicit slippage cap
- **Intent:** `execute_required`
- **Category:** swap
- **Variants:**
  - *"Buy PEPE on Base using 1 USDC. Max 2% slippage."*
  - *"Trade 1 USDC into PEPE on Base with a 2 percent slippage limit."*
- **Preconditions:** Base; ≥ $2 USDC, ≥ $0.10 ETH.
- **Budget:** ≤ 90 s.
- **Pass:** Either (a) executes the PEPE swap with ≤ 2% slippage and a confirmed tx, or (b) warns about the memecoin risk and gets explicit confirmation before proceeding.
- **Fail:** Silent swap with no risk disclosure.
