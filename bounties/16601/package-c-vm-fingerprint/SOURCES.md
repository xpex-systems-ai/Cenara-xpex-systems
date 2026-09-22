# Sources and Claim Map

All factual claims in the short should be checked against these public RustChain sources before final render/submission.

## 1. Protocol lifecycle / signed attestation
Source: https://github.com/Scottcjn/Rustchain/blob/main/docs/PROTOCOL.md
Relevant section: “2. RIP-200 Consensus” / “2.1 High-level lifecycle”.
Supports: miner collects hardware signals + fingerprint checks; submits signed attestation; node validates and enrolls eligible miner.

## 2. One CPU = one vote and reward weighting
Source: https://github.com/Scottcjn/Rustchain/blob/main/docs/PROTOCOL.md
Relevant sections: Overview and “2.2 Epoch settlement”.
Supports: baseline one CPU = one vote framing; reward weight influenced by validated hardware presence, antiquity multiplier, fingerprint confidence / anti-emulation checks.

## 3. Anti-VM economic treatment
Source: https://github.com/Scottcjn/Rustchain
Relevant section: “Anti-VM Enforcement”.
Supports: detected VMs receive an extremely small fraction of normal rewards.

Source: https://github.com/Scottcjn/Rustchain/blob/main/MANIFESTO.md
Relevant section: anti-emulation behavioral checks.
Supports: anti-emulation uses multiple behavioral/hardware signals and economically penalizes virtualized environments.

## Accuracy guardrails
- Do not claim that one individual signal proves physical hardware.
- Do not invent measured performance numbers.
- Do not imply guaranteed earnings or market value for RTC.
- If protocol wording changes before submission, update the script to match the current repository.
