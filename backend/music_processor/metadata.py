"""mutagen 元数据与歌词提取。"""

from pathlib import Path


def extract_metadata(file_path: str) -> dict[str, str]:
    """使用 mutagen Easy 模式提取 {title, artist, album}。"""
    try:
        from mutagen import File as MutagenFile
    except ImportError:
        return {"title": "未知", "artist": "未知", "album": "未知"}

    meta = {"title": "未知", "artist": "未知", "album": "未知"}
    try:
        audio = MutagenFile(file_path, easy=True)
        if audio is None:
            return meta
        if audio.get("title"):
            meta["title"] = str(audio["title"][0])
        if audio.get("artist"):
            meta["artist"] = str(audio["artist"][0])
        if audio.get("album"):
            meta["album"] = str(audio["album"][0])
        if meta["title"] == "未知":
            meta["title"] = Path(file_path).stem
    except Exception:
        meta["title"] = Path(file_path).stem
    return meta


def _get_text_from_tag_value(val) -> str:
    """从 mutagen 标签值安全提取文本。

    USLT 对象使用 .text 属性，普通值转 str()。
    """
    if val is None:
        return ""
    if hasattr(val, "text"):
        return str(val.text) if val.text else ""
    if isinstance(val, list):
        texts = []
        for item in val:
            if hasattr(item, "text"):
                texts.append(str(item.text))
            else:
                texts.append(str(item))
        return "\n".join(t for t in texts if t.strip())
    return str(val)


def extract_lyrics(file_path: str) -> str | None:
    """读取 MP3 USLT / FLAC LYRICS / M4A (c)lyr 内嵌歌词。"""
    try:
        from mutagen import File as MutagenFile
    except ImportError:
        return None
    try:
        audio = MutagenFile(file_path)
        if audio is None or not hasattr(audio, "tags") or not audio.tags:
            return None

        # ID3 USLT 标签
        for tag_name in ("USLT::eng", "USLT::XXX", "USLT::zho"):
            uslt = audio.tags.get(tag_name)
            if uslt:
                text = _get_text_from_tag_value(uslt)
                if text.strip():
                    return text

        # 兼容其他 USLT 语言代码
        for key in audio.tags:
            if key.startswith("USLT:"):
                val = audio.tags[key]
                text = _get_text_from_tag_value(val)
                if text.strip():
                    return text

        # FLAC / APE lyrics
        for lk in ("lyrics", "LYRICS"):
            val = audio.tags.get(lk)
            if val:
                text = _get_text_from_tag_value(val)
                if text.strip():
                    return text

        # M4A (c)lyr
        if "\xa9lyr" in audio.tags:
            val = audio.tags["\xa9lyr"]
            text = _get_text_from_tag_value(val)
            if text.strip():
                return text

    except Exception:
        pass
    return None
