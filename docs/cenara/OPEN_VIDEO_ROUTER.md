# Cenara Open Video Router

Cenara now treats open video models as interchangeable engines behind one button.

Priority:
1. Wan 2.2
2. LTX-2
3. Mochi 1
4. SkyReels
5. HunyuanVideo
6. existing Motion Storyboard fallback
7. local FFmpeg fallback

No local GPU is required by the Cenara web service. Each open model can be
connected through a remote HTTP endpoint:

- CENARA_WAN22_ENDPOINT
- CENARA_LTX2_ENDPOINT
- CENARA_MOCHI1_ENDPOINT
- CENARA_SKYREELS_ENDPOINT
- CENARA_HUNYUAN_ENDPOINT

Optional shared bearer token:
- CENARA_OPEN_VIDEO_API_TOKEN

Hugging Face Inference is also attempted when HF_TOKEN is available.

Important: open-source weights are free to inspect/use under their respective
licenses, but inference still needs compute somewhere. Cenara hides that detail
from the operator and falls back automatically when a remote engine is offline.
