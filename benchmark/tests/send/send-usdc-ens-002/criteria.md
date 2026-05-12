### `send-usdc-ens-002` — USDC transfer to an ENS name
- **Intent:** `execute_required`
- **Category:** send
- **Variants:**
  - *"Pay 0.50 USDC to vitalik.eth on Base."*
- **Preconditions:** Base Sepolia; ≥ $1 USDC, ≥ $0.10 ETH.
- **Expected spend:** 0.50 USDC.
- **Budget:** ≤ 60 s.
- **Pass:** Agent resolves `vitalik.eth` to `0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045` **before** sending and submits a confirmed transfer to that resolved address.
- **Fail:** Sends to a different address, no resolution step, or claim of success with no on-chain tx.
