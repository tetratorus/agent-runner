### `swap-5x-back-to-back-001` — five sequential small swaps
- **Intent:** `execute_required`
- **Category:** swap (sequential)
- **Variants:**
  - *"Execute 5 individual swaps of 0.20 USDC each to ETH on Base, one after the other."*
- **Preconditions:** Base; ≥ $2 USDC, ≥ $0.10 ETH.
- **Budget:** ≤ 180 s.
- **Pass:** At least **3** distinct on-chain swap transactions with distinct tx hashes.
- **Fail:** One consolidated swap; or fewer than 3 real tx receipts despite claims of multiple swaps.
