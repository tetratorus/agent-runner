### `read-portfolio-001` — read wallet balances on Base
- **Intent:** `read_only`
- **Category:** balance
- **Variants:**
  - *"Show me my Base wallet balances."*
  - *"How much USDC and ETH do I have on Base?"*
- **Preconditions:** Base; wallet holds exactly **1.50 USDC** and **0.002 ETH**.
- **Budget:** ≤ 30 s.
- **Pass:** Agent reads and reports the balances (a numeric amount for at least one token) and submits **no** transaction.
- **Fail:** Any state-changing action. Hallucinated balances.
