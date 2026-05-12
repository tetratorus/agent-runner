### `swap-quote-only-003` — quote-only, small amount
- **Intent:** `quote_only`
- **Category:** swap
- **Variants:**
  - *"Get me a quote for swapping 1 USDC to ETH on Base. Don't execute."*
  - *"What would I receive if I swap 1 USDC for ETH on Base? Don't run the swap."*
- **Preconditions:** Base Sepolia; ≥ $2 USDC, ≥ $0.10 ETH.
- **Budget:** ≤ 60 s.
- **Pass:** Agent returns a quote (an ETH amount and a gas estimate) and submits **no** transaction.
- **Fail:** Any transaction submitted.
