"""Ollama LLM 歌词意境分析 — 调用本地 qwen2:1.5b 提取意境标签。

POST http://localhost:11434/api/generate → 解析 JSON 数组 → 返回标签列表。
"""

import json
import logging
import re

import requests

logger = logging.getLogger("music_api")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2:1.5b"
MAX_LYRICS_CHARS = 2000  # 歌词截断长度，避免超出上下文窗口
REQUEST_TIMEOUT = 30  # 秒


def analyze_lyrics_via_llm(lyrics_text: str) -> list[str]:
    """调用 Ollama 分析歌词意境，返回标签列表（如 ["失恋", "黄昏", "孤独"]）。

    连接失败/超时/解析异常均自动降级返回空列表，不阻塞主流程。
    """
    if not lyrics_text or len(lyrics_text.strip()) < 20:
        return []

    # 截断歌词
    text = lyrics_text.strip()[:MAX_LYRICS_CHARS]

    prompt = f"""你是一个音乐意境分析专家。请根据以下歌词，提取 3-8 个核心意境标签（如：失恋、青春、热血、孤独、治愈、暗黑、浪漫、怀旧等）。
只输出一个 JSON 字符串数组，不要输出任何其他内容。

歌词：
{text}

输出示例：
["失恋", "黄昏", "孤独"]
"""

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "temperature": 0.3,
                "stream": False,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning(
                f"[LLM] Ollama 返回非 200: {resp.status_code}"
            )
            return []

        data = resp.json()
        response_text = data.get("response", "")
        if not response_text:
            return []

        tags = _parse_tags(response_text)
        logger.info(f"[LLM] 意境标签: {tags}")
        return tags

    except requests.exceptions.ConnectionError:
        logger.warning("[LLM] 无法连接 Ollama (localhost:11434)")
        return []
    except requests.exceptions.Timeout:
        logger.warning("[LLM] Ollama 请求超时")
        return []
    except Exception:
        logger.error(
            f"[LLM] 异常: {__import__('traceback').format_exc(limit=1)}"
        )
        return []


def _parse_tags(response_text: str) -> list[str]:
    """从 LLM 原始响应中解析 JSON 字符串数组。

    兼容格式：
    - 裸 JSON 数组：["失恋", "黄昏"]
    - Python set 语法：{"失恋", "黄昏"}
    - Markdown 代码块包裹：```json\n[...]\n```
    - 嵌入文本中：前面有杂散字符
    """
    text = response_text.strip()

    def _try_load_json(candidate: str) -> list | None:
        """尝试多种 JSON 格式解析。"""
        # 直接解析
        try:
            tags = json.loads(candidate)
            if isinstance(tags, list):
                return [str(t).strip() for t in tags if str(t).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        # Python set 语法 {"a","b"} → ["a","b"]
        try:
            fixed = candidate.replace("{", "[").replace("}", "]")
            tags = json.loads(fixed)
            if isinstance(tags, list):
                return [str(t).strip() for t in tags if str(t).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    # 1. 尝试直接解析整个文本
    result = _try_load_json(text)
    if result:
        return result

    # 2. Markdown 代码块
    code_m = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if code_m:
        result = _try_load_json(code_m.group(1))
        if result:
            return result

    # 3. 匹配大括号 { } 包裹的内容（Python set）
    set_m = re.search(r"\{[^}]+\}", text)
    if set_m:
        result = _try_load_json(set_m.group(0))
        if result:
            return result

    # 4. 匹配方括号 [ ] 包裹的内容（JSON array）
    arr_m = re.search(r"\[.*?\]", text, re.DOTALL)
    if arr_m:
        result = _try_load_json(arr_m.group(0))
        if result:
            return result

    logger.warning(f"[LLM] 无法解析标签: {text[:200]}")
    return []
