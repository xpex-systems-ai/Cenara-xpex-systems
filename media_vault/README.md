# XPEX Media Vault / Cenara Memory

This directory registers media supplied by the XPEX operator and gives Cenara a safe retrieval layer.

## Flow
1. Register source URLs in `drive_manifest.json`.
2. Ingest only files that are directly accessible to the runtime.
3. Probe technical metadata with ffprobe.
4. Mark every item `review_required` by default for commercial rights.
5. Later scene indexing can add semantic tags/embeddings and split videos into reusable clips.

## Security / rights
A registered URL is **not automatically approved for commercial reuse**.
Items must be classified as XPEX-owned, client-authorized, third-party, or review-required before use in paid work.
