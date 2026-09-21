# Cenara MuseTalk production lip-sync

## Production choice

MuseTalk 1.5 is the default production lip-sync engine for XPeX Academy.
The upstream MuseTalk project is MIT licensed. The open-source Wav2Lip
weights are not enabled for XPeX production because upstream explicitly
restricts them to research/academic/personal use.

## Architecture

Cenara CPU service -> HTTP -> MuseTalk GPU worker -> MP4 -> Academy composer.

The current Cenara Railway service is intentionally kept light. Configure:

- `CENARA_MUSETALK_API_URL=https://<gpu-worker-domain>`
- `CENARA_MUSETALK_API_TOKEN=<shared-secret>`
- `CENARA_MUSETALK_VERSION=v15`

The worker uses `Dockerfile.musetalk` and exposes:

- `GET /health`
- `POST /lipsync` multipart fields: `face`, `audio`, `version=v15`

## GPU requirement

MuseTalk upstream recommends Python 3.10 + CUDA and documents 4 GB VRAM
as a tested minimum for the demo. Use an NVIDIA GPU worker; do not deploy
this image onto the 1 GB RAM CPU-only Cenara web service.
