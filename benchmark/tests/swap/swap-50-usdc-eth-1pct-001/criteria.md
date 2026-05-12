### `swap-50-usdc-eth-1pct-001` — small swap with explicit 1% slippage
- **Intent:** `execute_required`
- **Category:** swap
- **Variants:**
  - *"Swap 0.50 USDC for ETH on Base with 1% slippage tolerance."*
  - *"Swap 0.50 USDC for ETH on Base, max 1% slippage."*
- **Preconditions:** Base Sepolia; ≥ $2 USDC, ≥ $0.10 ETH.
- **Budget:** ≤ 60 s.
- **Pass:** Confirmed swap honouring the 1% slippage instruction.
- **Fail:** No tx, or slippage exceeded.
