from __future__ import annotations

import json, os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import requests
from loguru import logger

HANDOFF_VERSION='XPEX-ACADEMY-HANDOFF-1.0'

@dataclass
class ShotSpec:
    id:str; type:str; duration:float; narration:str; visual_prompt:str
    camera:str='slow dolly'; transition:str='cut'; overlay:str=''; avatar:bool=False; broll:bool=False

@dataclass
class AcademyHandoff:
    version:str; project_id:str; title:str; topic:str; objective:str; audience:str; duration_minutes:int; language:str; voice:str; aspect_ratio:str; master_format:str; visual_profile:str; instructor_style:str
    pedagogical_arc:list[str]=field(default_factory=list); shots:list[ShotSpec]=field(default_factory=list); render_policy:dict[str,Any]=field(default_factory=dict); quality_gates:dict[str,Any]=field(default_factory=dict)

def _clean(v): return ' '.join(str(v or '').split()).strip()

def _fallback(topic, objective, minutes, voice):
    texts=[f'Bem-vindo à XPeX Academy. Nesta aula vamos entender {topic}.','Começamos pelo conceito principal e por que ele importa na prática.','Agora veja uma comparação visual que organiza as ideias essenciais.','Vamos aplicar o conceito em uma situação concreta do dia a dia.','Observe este exemplo visual e identifique entrada, processo e resultado.','Para fechar, revise os pontos principais e conecte com a próxima aula.']
    kinds=['talking_head','support_visual','talking_head','support_visual','support_visual','talking_head']
    sec=max(18.0,(minutes*60)/len(texts)); shots=[]
    for i,(kind,text) in enumerate(zip(kinds,texts),1):
        shots.append(ShotSpec(f'S{i:02d}',kind,round(sec,2),text,f'{topic}, professional aerospace-documentary educational cinematography, real materials, clean optics, restrained depth of field, Roman precision profile, no text', ['locked medium','slow dolly','macro slider','controlled handheld','top-down precision','slow push-in'][(i-1)%6], 'cut' if i%3 else 'crossfade', '' if kind=='talking_head' else 'keyword', kind=='talking_head', kind!='talking_head'))
    return AcademyHandoff(HANDOFF_VERSION,'academy-'+str(abs(hash(topic)))[:10],topic,topic,objective or 'Ensinar o tema de forma clara, prática e memorável.','Aluno iniciante/intermediário da XPeX Academy',minutes,'pt-BR',voice,'16:9','1920x1080_29.97fps_h264_aac48k','roman_precision','professor direto, natural, confiante e didático',['gancho','conceito','comparação','aplicação','exemplo','recap'],shots,{'video_router':['cosmos3','wan22','skyreelsv3','ltx2','skyreels','mochi1','hunyuan'],'avatar_router':['echomimic_v3','liveavatar','musetalk_v15','liveportrait'],'fallback':'xpex_premium_dynamic_compositor','max_static_seconds':6},{'no_gibberish_text':True,'no_deformed_faces':True,'subject_continuity':True,'audio_required':True,'target_master':'1920x1080'})

def build_handoff(topic, objective, minutes, voice):
    topic=_clean(topic); objective=_clean(objective); fallback=_fallback(topic,objective,minutes,voice)
    key=_clean(os.getenv('OPENROUTER_API_KEY',''))
    if not key: return fallback
    system='Você é a Cenara Director Agent. Responda SOMENTE JSON válido. Crie 8 a 14 shots curtos em pt-BR, alternando talking_head e support_visual. Cada shot: id,type,duration,narration,visual_prompt,camera,transition,overlay,avatar,broll. Visual_prompt em inglês, documental, realista, sem texto na imagem.'
    user=json.dumps({'topic':topic,'objective':objective,'minutes':minutes,'visual_profile':'roman_precision','master':'1920x1080_29.97fps'},ensure_ascii=False)
    try:
        r=requests.post('https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','X-Title':'Cenara Director Agent'},json={'model':os.getenv('OPENROUTER_MODEL','openrouter/free'),'messages':[{'role':'system','content':system},{'role':'user','content':user}],'temperature':0.35,'max_tokens':4200},timeout=(12,35))
        if r.status_code>=400: return fallback
        raw=str((((r.json().get('choices') or [{}])[0].get('message') or {}).get('content')) or '').strip(); a,b=raw.find('{'),raw.rfind('}')
        if a>=0 and b>a: raw=raw[a:b+1]
        data=json.loads(raw); incoming=data.get('shots') or []
        if not isinstance(incoming,list) or len(incoming)<4: return fallback
        shots=[]
        for i,x in enumerate(incoming[:16],1):
            if not isinstance(x,dict): continue
            shots.append(ShotSpec(_clean(x.get('id')) or f'S{i:02d}',_clean(x.get('type')) or 'support_visual',float(x.get('duration') or max(8,(minutes*60)/max(1,len(incoming)))),_clean(x.get('narration')),_clean(x.get('visual_prompt')) or fallback.shots[min(i-1,len(fallback.shots)-1)].visual_prompt,_clean(x.get('camera')) or 'slow dolly',_clean(x.get('transition')) or 'cut',_clean(x.get('overlay')),bool(x.get('avatar')),bool(x.get('broll'))))
        if len(shots)>=4: fallback.shots=shots; fallback.title=_clean(data.get('title')) or fallback.title
        return fallback
    except Exception as exc:
        logger.warning(f'handoff director fallback: {type(exc).__name__}'); return fallback

def validate_handoff(h):
    errors=[]; total=sum(max(0,float(s.duration)) for s in h.shots); target=h.duration_minutes*60
    if h.version!=HANDOFF_VERSION: errors.append('version inválida')
    if not h.topic: errors.append('topic ausente')
    if not h.shots: errors.append('shots ausentes')
    if total<target*0.45 or total>target*1.8: errors.append('timeline fora da faixa')
    for s in h.shots:
        if s.type not in {'talking_head','support_visual'}: errors.append(f'shot {s.id}: type inválido')
        if not s.narration: errors.append(f'shot {s.id}: narration ausente')
    return errors

def save_handoff(h,path:Path):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(asdict(h),ensure_ascii=False,indent=2),encoding='utf-8'); return path
