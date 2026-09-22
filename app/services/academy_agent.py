from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from app.services.academy_handoff import build_handoff, save_handoff, validate_handoff
from app.services.academy_lesson import create_academy_lesson

class AcademyAgentError(RuntimeError):
    pass

def run_academy_agent(topic:str, objective:str, minutes:int, voice:str, avatar_enabled:bool=True):
    handoff=build_handoff(topic,objective,minutes,voice)
    errors=validate_handoff(handoff)
    if errors: raise AcademyAgentError('Handoff inválido: '+'; '.join(errors[:8]))
    output,manifest=create_academy_lesson(topic=handoff.topic,objective=handoff.objective,minutes=handoff.duration_minutes,voice_name=handoff.voice,voice_rate=1.0,avatar_enabled=avatar_enabled,handoff=asdict(handoff))
    handoff_path=output.parent/'academy-handoff.json'; save_handoff(handoff,handoff_path)
    manifest['handoff_version']=handoff.version; manifest['handoff_path']=str(handoff_path); manifest['agent_mode']='cenara_academy_specialist_v1'
    (output.parent/'lesson-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return output,manifest,handoff_path
