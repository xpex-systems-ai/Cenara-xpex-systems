import json
import math
import os
import os.path
import shutil
import re
import contextlib
from os import path

from loguru import logger

from app.config import config
from app.models import const
from app.models.schema import VideoConcatMode, VideoParams
from app.services import llm, material, subtitle, twelvelabs, video, voice, upload_post
from app.services import state as sm
from app.services.runtime_limits import get_runtime_limits
from app.services.railway_render import ffprobe_validate_mp4, normalize_survival_aspect, render_survival_mp4
from app.utils import file_security, utils



def cenara_collect_referenced_task_files(task_state: dict | None) -> set[str]:
    referenced: set[str] = set()
    if not isinstance(task_state, dict):
        return referenced
    for key in ("videos", "combined_videos", "output_path", "preview_path", "browser_preview_path", "download_path"):
        value = task_state.get(key)
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, str) and item:
                referenced.add(os.path.realpath(item))
                if item.endswith(".mp4"):
                    root, ext = os.path.splitext(item)
                    referenced.add(os.path.realpath(f"{root}.browser{ext}"))
    return referenced


def cenara_is_referenced_artifact(file_path: str, referenced_files: set[str]) -> bool:
    return os.path.realpath(file_path) in referenced_files


def cenara_locked_generation_task_id() -> str | None:
    lock_path = os.path.join(utils.storage_dir(create=True), "cenara_runtime", "generation.lock")
    try:
        with open(lock_path, "r", encoding="utf-8") as lock_file:
            data = json.load(lock_file)
        task_id = data.get("task_id")
        return task_id if isinstance(task_id, str) and task_id else None
    except FileNotFoundError:
        return None
    except Exception as exc:
        logger.debug(f"Cenara prune could not read generation lock: {type(exc).__name__}")
        return None


def prune_cenara_storage(active_task_id: str | None = None) -> dict:
    limits = get_runtime_limits()
    report = {"deleted": 0, "kept_tasks": 0}
    storage_root = utils.storage_dir(create=True)
    cache_root = utils.storage_dir("cache_videos", create=True)
    tasks_root = utils.storage_dir("tasks", create=True)
    active_task_ids = {active_task_id} if active_task_id else set()
    locked_task_id = cenara_locked_generation_task_id()
    if locked_task_id:
        active_task_ids.add(locked_task_id)
    referenced_files: set[str] = set()
    for protected_task_id in active_task_ids:
        protected_task_state = sm.state.get_task(protected_task_id)
        referenced_files.update(cenara_collect_referenced_task_files(protected_task_state))

    def safe_remove(file_path: str):
        try:
            real = os.path.realpath(file_path)
            if not real.startswith(os.path.realpath(storage_root)):
                return
            os.remove(real)
            report["deleted"] += 1
        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.debug(f"Cenara prune skipped file: {type(exc).__name__}")

    for root, _, files in os.walk(cache_root):
        for name in files:
            file_path = os.path.join(root, name)
            size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            if name.endswith(".part") or size == 0 or (name.endswith(".mp4") and size > limits.max_remote_video_bytes):
                safe_remove(file_path)

    task_dirs = []
    if os.path.isdir(tasks_root):
        for name in os.listdir(tasks_root):
            full = os.path.join(tasks_root, name)
            if os.path.isdir(full):
                task_dirs.append((os.path.getmtime(full), name, full))
    task_dirs.sort(reverse=True)
    keep = {name for _, name, _ in task_dirs[:limits.prune_tasks_keep]}
    keep.update(active_task_ids)
    report["kept_tasks"] = len(keep)
    for _, name, full in task_dirs:
        if name in active_task_ids:
            continue
        if name in keep:
            for pattern in (".part",):
                pass
            for root, _, files in os.walk(full):
                for file_name in files:
                    f = os.path.join(root, file_name)
                    if cenara_is_referenced_artifact(f, referenced_files):
                        continue
                    if file_name.endswith(".part") or file_name.startswith("temp-clip-") or file_name.startswith("combined-") or (file_name.endswith(".mp4") and os.path.getsize(f) == 0):
                        safe_remove(f)
            continue
        try:
            shutil.rmtree(full)
            report["deleted"] += 1
        except Exception as exc:
            logger.debug(f"Cenara prune skipped task dir: {type(exc).__name__}")
    logger.info(f"Cenara storage prune report: deleted={report['deleted']} kept_tasks={report['kept_tasks']}")
    return report

def derive_safe_video_terms(*texts, limit: int = 6):
    stop_words = {"para", "com", "uma", "que", "seu", "sua", "dos", "das", "por", "the", "and", "you", "your", "with"}
    words = []
    source = " ".join(str(text or "") for text in texts)
    source = re.sub(r"https?://\S+|www\.\S+|\S+@\S+", " ", source)
    for word in re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", source.lower()):
        if len(word) > 20 or re.fullmatch(r"[a-z0-9_-]{18,}", word):
            continue
        if word not in words and word not in stop_words:
            words.append(word)
        if len(words) >= limit:
            break
    return words


def generate_script(task_id, params):
    logger.info("\n\n## generating video script")
    video_script = params.video_script.strip()
    if not video_script:
        video_script = llm.generate_script(
            video_subject=params.video_subject,
            language=params.video_language,
            paragraph_number=params.paragraph_number,
            video_script_prompt=params.video_script_prompt,
            custom_system_prompt=params.custom_system_prompt,
        )
    else:
        logger.debug(f"video script: \n{video_script}")

    if not video_script:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        logger.error("failed to generate video script.")
        return None

    return video_script


def generate_terms(task_id, params, video_script):
    logger.info("\n\n## generating video terms")
    video_terms = params.video_terms
    manual_script_mode = bool((params.video_script or "").strip())
    if not video_terms and manual_script_mode:
        video_terms = derive_safe_video_terms(params.video_subject, video_script)
        if video_terms:
            params.video_terms = video_terms
            logger.info("manual script mode: derived local video terms without LLM")
    if not video_terms:
        if manual_script_mode:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error("Informe palavras-chave manuais para buscar mídia sem chamar o LLM.")
            return None
        # 开启素材按文案顺序匹配后，关键词本身也必须按脚本叙事顺序生成；
        # 否则后续即使顺序下载和顺序拼接，也只能复用一组全局主题词，
        # 无法改善“后面内容的画面提前出现”的问题。
        video_terms = llm.generate_terms(
            video_subject=params.video_subject,
            video_script=video_script,
            amount=8 if params.match_materials_to_script else 5,
            match_script_order=params.match_materials_to_script,
        )
    else:
        if isinstance(video_terms, str):
            video_terms = [term.strip() for term in re.split(r"[,，]", video_terms)]
        elif isinstance(video_terms, list):
            video_terms = [term.strip() for term in video_terms]
        else:
            raise ValueError("video_terms must be a string or a list of strings.")

        logger.debug(f"video terms: {utils.to_json(video_terms)}")

    if not video_terms:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        logger.error("failed to generate video terms.")
        return None

    # 可选的 TwelveLabs Marengo 语义重排：未启用时返回原顺序，无任何副作用。
    # 顺序匹配模式下关键词顺序本身就是脚本叙事顺序，必须保持原样，故跳过。
    if not params.match_materials_to_script and not manual_script_mode:
        video_terms = twelvelabs.rerank_terms_by_subject(
            video_subject=params.video_subject,
            search_terms=video_terms,
        )

    return video_terms


def save_script_data(task_id, video_script, video_terms, params):
    script_file = path.join(utils.task_dir(task_id), "script.json")
    script_data = {
        "script": video_script,
        "search_terms": video_terms,
        "params": params,
    }

    with open(script_file, "w", encoding="utf-8") as f:
        f.write(utils.to_json(script_data))


def resolve_custom_audio_file(task_id: str, custom_audio_file: str | None) -> str:
    requested_file = (custom_audio_file or "").strip()
    if not requested_file:
        return ""

    task_dir = utils.task_dir(task_id)
    try:
        return file_security.resolve_path_within_directory(
            task_dir,
            requested_file,
        )
    except ValueError as exc:
        task_dir_error = exc

    server_audio_file = path.realpath(
        requested_file
        if path.isabs(requested_file)
        else path.join(utils.root_dir(), requested_file)
    )
    if not path.isabs(requested_file):
        project_root = path.realpath(utils.root_dir())
        try:
            if path.commonpath([project_root, server_audio_file]) != project_root:
                raise ValueError(
                    "relative custom audio paths must stay within the project directory"
                )
        except ValueError as exc:
            raise ValueError(
                "custom audio file must be task-local or an existing server-side file"
            ) from exc

    if not path.isfile(server_audio_file):
        raise ValueError(
            "custom audio file does not exist or is not a file"
        ) from task_dir_error

    return server_audio_file


def generate_audio(task_id, params, video_script):
    '''
    Generate audio for the video script.
    If a custom audio file is provided, it will be used directly.
    There will be no subtitle maker object returned in this case.
    Otherwise, TTS will be used to generate the audio.
    Returns:
        - audio_file: path to the generated or provided audio file
        - audio_duration: duration of the audio in seconds
        - sub_maker: subtitle maker object if TTS is used, None otherwise
    '''
    logger.info("\n\n## generating audio")
    # /audio 和 /subtitle 请求模型不包含 custom_audio_file，
    # 这里统一做兼容读取，避免直调接口时抛属性错误。
    requested_custom_audio_file = getattr(params, "custom_audio_file", None)
    try:
        custom_audio_file = resolve_custom_audio_file(
            task_id, requested_custom_audio_file
        )
    except ValueError as exc:
        logger.error(
            "custom audio file is invalid, "
            f"task_id: {task_id}, path: {requested_custom_audio_file}, error: {str(exc)}"
        )
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return None, None, None

    if not custom_audio_file:
        logger.info("no custom audio file provided, using TTS to generate audio.")
        audio_file = path.join(utils.task_dir(task_id), "audio.mp3")
        sub_maker = voice.tts(
            text=video_script,
            voice_name=voice.parse_voice_name(params.voice_name),
            voice_rate=params.voice_rate,
            voice_file=audio_file,
        )
        if sub_maker is None:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error(
                """failed to generate audio:
1. check if the language of the voice matches the language of the video script.
2. check if the network is available. If you are in China, it is recommended to use a VPN and enable the global traffic mode.
            """.strip()
            )
            return None, None, None
        audio_duration = math.ceil(voice.get_audio_duration(sub_maker))
        if audio_duration == 0:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error("failed to get audio duration.")
            return None, None, None
        return audio_file, audio_duration, sub_maker
    else:
        logger.info(f"using custom audio file: {custom_audio_file}")
        audio_duration = voice.get_audio_duration(custom_audio_file)
        if audio_duration == 0:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error("failed to get audio duration from custom audio file.")
            return None, None, None
        return custom_audio_file, audio_duration, None

def generate_subtitle(task_id, params, video_script, sub_maker, audio_file, audio_duration=None):
    """Generate subtitles without allowing transcription failures to kill MP4 rendering."""
    logger.info("\n\n## generating subtitle")
    limits = get_runtime_limits()
    if not getattr(params, "subtitle_enabled", True):
        sm.state.update_task(task_id, subtitle_status="disabled", subtitle_skipped=True, subtitle_path="")
        return ""

    subtitle_path = path.join(utils.task_dir(task_id), "subtitle.srt")

    def skip(code: str, message: str):
        logger.warning(f"subtitle_skipped_non_blocking: {code} {message}")
        sm.state.update_task(task_id, subtitle_status="skipped_non_blocking", subtitle_skipped=True, subtitle_error_code=code, safe_message=message)
        return ""

    try:
        if limits.disable_local_whisper or limits.subtitle_engine == "script_estimate":
            result = subtitle.generate_estimated_srt_from_script(video_script, audio_duration, subtitle_path)
            sm.state.update_task(task_id, subtitle_result=result, subtitle_status="ready" if result.get("ok") else "skipped_non_blocking")
            return result.get("path", "") if result.get("ok") else skip(result.get("error_code", "ESTIMATE_FAILED"), result.get("message", "Legendas estimadas indisponíveis."))

        subtitle_provider = config.app.get("subtitle_provider", "edge").strip().lower()
        logger.info(f"\n\n## generating subtitle, provider: {subtitle_provider}")
        if sub_maker is None and subtitle_provider != "whisper":
            return skip("SUBTITLE_TIMELINE_MISSING", f"subtitle maker missing for provider {subtitle_provider}")
        subtitle_fallback = False
        if subtitle_provider == "edge":
            voice.create_subtitle(text=video_script, sub_maker=sub_maker, subtitle_file=subtitle_path)
            if not os.path.exists(subtitle_path):
                subtitle_fallback = True
                logger.warning("subtitle file not found; whisper fallback considered")
        if subtitle_provider == "whisper" or subtitle_fallback:
            if limits.disable_local_whisper:
                return skip("LOCAL_WHISPER_DISABLED", "Whisper local desativado neste runtime.")
            subtitle.create(audio_file=audio_file, subtitle_file=subtitle_path)
            if os.path.exists(subtitle_path):
                subtitle.correct(subtitle_file=subtitle_path, video_script=video_script)
        if not subtitle.file_to_subtitles(subtitle_path):
            return skip("INVALID_SUBTITLE", f"subtitle file invalid: {subtitle_path}")
        sm.state.update_task(task_id, subtitle_status="ready", subtitle_path=subtitle_path)
        return subtitle_path
    except Exception as exc:
        if limits.skip_subtitle_on_failure or limits.subtitles_optional:
            return skip(type(exc).__name__, "Falha de legenda ignorada; renderização continuará sem legendas.")
        raise


def get_video_materials(task_id, params, video_terms, audio_duration):
    if params.video_source == "local":
        logger.info("\n\n## preprocess local materials")
        materials = video.preprocess_video(
            materials=params.video_materials, clip_duration=params.video_clip_duration
        )
        if not materials:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error(
                "no valid materials found, please check the materials and try again."
            )
            return None
        return [material_info.url for material_info in materials]
    else:
        logger.info(f"\n\n## downloading videos from {params.video_source}")
        # 顺序匹配模式只在用户显式开启时生效。这里强制素材下载按关键词顺序
        # 轮询，避免某个早期关键词下载太多素材，把后续脚本主题挤出最终时间线。
        downloaded_videos = material.download_videos(
            task_id=task_id,
            search_terms=video_terms,
            source=params.video_source,
            video_aspect=params.video_aspect,
            video_concat_mode=(
                VideoConcatMode.sequential
                if params.match_materials_to_script
                else params.video_concat_mode
            ),
            audio_duration=audio_duration * params.video_count,
            max_clip_duration=params.video_clip_duration,
            match_script_order=params.match_materials_to_script,
        )
        if not downloaded_videos:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error(
                "failed to download videos, maybe the network is not available. if you are in China, please use a VPN."
            )
            return None
        return downloaded_videos


def _cenara_use_survival_renderer() -> bool:
    limits = get_runtime_limits()
    return limits.low_memory_mode or limits.render_engine == "ffmpeg_survival"


def generate_survival_video(task_id, params, downloaded_videos, audio_file, subtitle_path, audio_duration):
    valid_sources = [video_path for video_path in downloaded_videos or [] if isinstance(video_path, str) and os.path.isfile(video_path) and os.path.getsize(video_path) > 0]
    output_path = path.join(utils.task_dir(task_id), f"cenara-final-{task_id}.mp4")
    part_path = f"{output_path}.part"
    if getattr(params, "video_source", "") == "frontier_ai" and valid_sources:
        # Frontier providers already return a finished cinematic MP4, frequently
        # with native synchronized audio. Preserve the provider master instead of
        # downscaling/re-encoding it through Railway survival mode.
        try:
            shutil.copy2(valid_sources[0], output_path)
            validation = ffprobe_validate_mp4(output_path)
            if validation.get("valid"):
                sm.state.update_task(
                    task_id,
                    render_engine="frontier_direct",
                    render_started=True,
                    mp4_created=True,
                    output_path=output_path,
                    frontier_master_preserved=True,
                )
                return [output_path], []
        except Exception as exc:
            logger.warning(f"frontier direct master fallback: {type(exc).__name__}")
        with contextlib.suppress(FileNotFoundError):
            os.remove(output_path)
    with contextlib.suppress(FileNotFoundError):
        os.remove(part_path)
    if not valid_sources:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED, render_engine="ffmpeg_survival", render_started=True, mp4_created=False, safe_error_code="NO_PROVIDER_VIDEO")
        with contextlib.suppress(FileNotFoundError):
            if os.path.exists(output_path) and os.path.getsize(output_path) == 0:
                os.remove(output_path)
        return [], []
    sm.state.update_task(task_id, render_engine="ffmpeg_survival", render_started=True, mp4_created=False, combined_videos=[])
    duration = float(audio_duration) if audio_duration and float(audio_duration) > 0 else float(params.video_clip_duration or 3)
    aspect = normalize_survival_aspect(params.video_aspect)
    result = render_survival_mp4(task_id, valid_sources[0], audio_file, subtitle_path, output_path, duration, aspect=aspect)
    if not result.get("success"):
        with contextlib.suppress(FileNotFoundError):
            os.remove(part_path)
        if os.path.exists(output_path) and os.path.getsize(output_path) == 0:
            with contextlib.suppress(FileNotFoundError):
                os.remove(output_path)
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED, render_engine="ffmpeg_survival", render_started=True, mp4_created=False, safe_error_code=result.get("safe_error_code", "SURVIVAL_RENDER_FAILED"), safe_message=result.get("safe_message", "Render survival falhou."))
        return [], []
    validation = ffprobe_validate_mp4(output_path)
    if not validation.get("valid"):
        with contextlib.suppress(FileNotFoundError):
            os.remove(output_path)
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED, render_engine="ffmpeg_survival", render_started=True, mp4_created=False, safe_error_code=validation.get("reason", "INVALID_FINAL_MP4"))
        return [], []
    sm.state.update_task(task_id, render_engine="ffmpeg_survival", render_started=True, mp4_created=True, output_path=output_path, survival_render=result)
    return [output_path], []


def generate_final_videos(
    task_id, params, downloaded_videos, audio_file, subtitle_path
):
    get_runtime_limits()
    final_video_paths = []
    combined_video_paths = []
    # 多视频生成默认会打散素材以增加差异；但“按文案顺序匹配素材”追求的是
    # 时间线稳定性和可解释性，所以开启后所有输出都使用顺序拼接。
    if params.match_materials_to_script:
        video_concat_mode = VideoConcatMode.sequential
    elif params.video_count == 1:
        video_concat_mode = params.video_concat_mode
    else:
        video_concat_mode = VideoConcatMode.random
    video_transition_mode = params.video_transition_mode

    _progress = 50
    for i in range(params.video_count):
        index = i + 1
        combined_video_path = path.join(
            utils.task_dir(task_id), f"combined-{index}.mp4"
        )
        logger.info(f"\n\n## combining video: {index} => {combined_video_path}")
        video.combine_videos(
            combined_video_path=combined_video_path,
            video_paths=downloaded_videos,
            audio_file=audio_file,
            video_aspect=params.video_aspect,
            video_concat_mode=video_concat_mode,
            video_transition_mode=video_transition_mode,
            max_clip_duration=params.video_clip_duration,
            threads=get_runtime_limits().render_threads if get_runtime_limits().low_memory_mode else params.n_threads,
        )

        _progress += 50 / params.video_count / 2
        sm.state.update_task(task_id, progress=_progress)

        final_video_path = path.join(utils.task_dir(task_id), f"final-{index}.mp4")

        logger.info(f"\n\n## generating video: {index} => {final_video_path}")
        video.generate_video(
            video_path=combined_video_path,
            audio_path=audio_file,
            subtitle_path=subtitle_path,
            output_file=final_video_path,
            params=params,
        )

        _progress += 50 / params.video_count / 2
        sm.state.update_task(task_id, progress=_progress)

        if os.path.getsize(final_video_path) > get_runtime_limits().max_output_mp4_bytes:
            logger.warning("download_blocked_for_memory: generated MP4 exceeds configured output cap")
        final_video_paths.append(final_video_path)
        combined_video_paths.append(combined_video_path)

    protected_paths = final_video_paths + combined_video_paths
    video._cleanup_render_artifacts(utils.task_dir(task_id), protected_paths=protected_paths)
    existing_combined_video_paths = [path for path in combined_video_paths if os.path.exists(path)]
    return final_video_paths, existing_combined_video_paths


def start(task_id, params: VideoParams, stop_at: str = "video"):
    logger.info(f"start task: {task_id}, stop_at: {stop_at}")
    if get_runtime_limits().low_memory_mode:
        params.n_threads = get_runtime_limits().render_threads
    prune_cenara_storage(active_task_id=task_id)
    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=5)

    # 1. Generate script
    video_script = generate_script(task_id, params)
    if not video_script or "Error: " in video_script:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=10)

    if stop_at == "script":
        sm.state.update_task(
            task_id, state=const.TASK_STATE_COMPLETE, progress=100, script=video_script
        )
        return {"script": video_script}

    # 2. Generate terms
    video_terms = ""
    if params.video_source != "local":
        video_terms = generate_terms(task_id, params, video_script)
        if not video_terms:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            return

    save_script_data(task_id, video_script, video_terms, params)

    if stop_at == "terms":
        sm.state.update_task(
            task_id, state=const.TASK_STATE_COMPLETE, progress=100, terms=video_terms
        )
        return {"script": video_script, "terms": video_terms}

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=20)

    # 3. Generate audio
    audio_file, audio_duration, sub_maker = generate_audio(
        task_id, params, video_script
    )
    if not audio_file:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=30)

    if stop_at == "audio":
        sm.state.update_task(
            task_id,
            state=const.TASK_STATE_COMPLETE,
            progress=100,
            audio_file=audio_file,
        )
        return {"audio_file": audio_file, "audio_duration": audio_duration}

    # 4. Generate subtitle
    subtitle_path = generate_subtitle(
        task_id, params, video_script, sub_maker, audio_file, audio_duration
    )

    if stop_at == "subtitle":
        sm.state.update_task(
            task_id,
            state=const.TASK_STATE_COMPLETE,
            progress=100,
            subtitle_path=subtitle_path,
        )
        return {"subtitle_path": subtitle_path}

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=40)

    # 5. Get video materials
    downloaded_videos = get_video_materials(
        task_id, params, video_terms, audio_duration
    )
    if not downloaded_videos:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return

    if stop_at == "materials":
        sm.state.update_task(
            task_id,
            state=const.TASK_STATE_COMPLETE,
            progress=100,
            materials=downloaded_videos,
        )
        return {"materials": downloaded_videos}

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=50)

    # 仅完整视频生成流程才需要处理视频拼接模式；
    # 这样可以避免 /subtitle 和 /audio 这类请求访问不存在的字段。
    if type(params.video_concat_mode) is str:
        params.video_concat_mode = VideoConcatMode(params.video_concat_mode)

    # 6. Generate final videos
    if _cenara_use_survival_renderer():
        final_video_paths, combined_video_paths = generate_survival_video(
            task_id, params, downloaded_videos, audio_file, subtitle_path, audio_duration
        )
    else:
        final_video_paths, combined_video_paths = generate_final_videos(
            task_id, params, downloaded_videos, audio_file, subtitle_path
        )

    if not final_video_paths:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return

    logger.success(
        f"task {task_id} finished, generated {len(final_video_paths)} videos."
    )

    # 7. Cross-post to social platforms (if enabled)
    cross_post_results = []
    if upload_post.upload_post_service.is_configured() and upload_post.upload_post_service.auto_upload:
        platforms = upload_post.upload_post_service.platforms
        logger.info(f"\n\n## cross-posting videos to {', '.join(platforms)}")

        youtube_extra = None
        if any(p.startswith("youtube") for p in platforms):
            metadata = llm.generate_social_metadata(
                video_subject=params.video_subject,
                video_script=video_script,
                language=params.video_language or "",
                platform="youtube_shorts",
            )
            youtube_extra = {
                "youtube_title": metadata.get("title", params.video_subject),
                "youtube_description": metadata.get("caption", ""),
                "tags": metadata.get("hashtags", []),
                "privacyStatus": upload_post.upload_post_service.youtube_privacy_status,
                "containsSyntheticMedia": True,
            }

        for video_path in final_video_paths:
            result = upload_post.cross_post_video(
                video_path=video_path,
                title=params.video_subject or "Check out this video! #shorts #viral",
                youtube_extra=youtube_extra,
            )
            cross_post_results.append(result)
            if result.get('success'):
                logger.info(f"✅ Cross-posted: {video_path}")
            else:
                logger.warning(f"⚠️ Failed to cross-post: {video_path} - {result.get('error', 'Unknown error')}")

    kwargs = {
        "videos": final_video_paths,
        **({} if _cenara_use_survival_renderer() else {"combined_videos": combined_video_paths}),
        "render_engine": "ffmpeg_survival" if _cenara_use_survival_renderer() else "moviepy",
        "mp4_created": True,
        "script": video_script,
        "terms": video_terms,
        "audio_file": audio_file,
        "audio_duration": audio_duration,
        "subtitle_path": subtitle_path,
        "materials": downloaded_videos,
        "cross_post_results": cross_post_results if cross_post_results else None,
    }
    sm.state.update_task(
        task_id, state=const.TASK_STATE_COMPLETE, progress=100, **kwargs
    )
    return kwargs


if __name__ == "__main__":
    task_id = "task_id"
    params = VideoParams(
        video_subject="金钱的作用",
        voice_name="zh-CN-XiaoyiNeural-Female",
        voice_rate=1.0,
    )
    start(task_id, params, stop_at="video")
