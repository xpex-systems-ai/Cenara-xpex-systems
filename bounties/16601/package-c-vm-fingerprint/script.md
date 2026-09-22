# Script — “Why a VM can't fake vintage hardware on RustChain”

**Target duration:** 45–55 seconds  
**Format:** 9:16 vertical, 1080x1920

**HOOK (0–6s)**  
What stops someone from spinning up a thousand virtual machines and pretending they're rare vintage computers?

**BODY (6–18s)**  
RustChain's answer is Proof-of-Antiquity. A miner collects hardware signals, runs fingerprint checks, and submits a signed attestation before it can participate in an epoch.

**BODY (18–34s)**  
The protocol doesn't rely on CPU speed alone. Its documentation says baseline participation follows one CPU, one vote, while reward weight also depends on validated hardware presence, antiquity, fingerprint confidence, and anti-emulation checks.

**BODY (34–46s)**  
That makes synthetic scale expensive instead of useful: the public RustChain documentation says detected virtual machines receive only a tiny fraction of normal mining rewards.

**CLOSE (46–55s)**  
The idea is simple: prove the machine is real, then reward scarce physical hardware. That's Proof-of-Antiquity.

**On-screen disclaimer:** “Technical summary based on RustChain public documentation. Verify current protocol rules in the linked sources.”
