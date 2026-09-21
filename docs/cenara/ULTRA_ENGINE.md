# Cenara Ultra Engine

This is a routing/orchestration layer, not quantum computing.

## Video priority
1. NVIDIA Cosmos 3 (when a compatible endpoint is configured)
2. Wan 2.2
3. SkyReels V3
4. LTX-2
5. SkyReels V2
6. Mochi 1
7. HunyuanVideo
8. XPeX premium dynamic compositor fallback

## Avatar priority
1. EchoMimicV3
2. LiveAvatar
3. MuseTalk 1.5
4. LivePortrait
5. XPeX presenter-motion fallback

## Roman Precision visual profile
The profile borrows the design philosophy of modern scientific imaging:
clean optics, high dynamic range, controlled highlights, deep blacks,
precise geometry and continuity. It does not use NASA hardware or quantum
computing.

## Environment variables
- CENARA_ULTRA_VISUAL_PROFILE=roman_precision
- CENARA_OPEN_VIDEO_MODEL=cosmos3
- CENARA_COSMOS3_ENDPOINT
- CENARA_SKYREELSV3_ENDPOINT
- CENARA_WAN22_ENDPOINT
- CENARA_LTX2_ENDPOINT
- CENARA_ECHOMIMIC_V3_ENDPOINT
- CENARA_LIVEAVATAR_ENDPOINT
- CENARA_MUSETALK_API_URL
- CENARA_LIVEPORTRAIT_ENDPOINT
