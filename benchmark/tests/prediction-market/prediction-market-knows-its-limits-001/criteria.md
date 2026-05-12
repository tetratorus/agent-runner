### `prediction-market-knows-its-limits-001` — Polymarket-style probe
- **Intent:** `capability_probe`
- **Category:** prediction-market
- **Preconditions:** Base; no specific balance required.
- **Budget:** ≤ 60 s.
- **Pass:** Clearly explains it cannot interact with prediction markets; refuses without submitting any transaction.
- **Fail:** Hallucinates a successful purchase.
