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
        for tag_name in ("USLT::eng", "USLT::XXX", "USLT::zho"):
            uslt = audio.tags.get(tag_name)
            if uslt:
                return str(uslt)
        for key in audio.tags:
            if key.startswith("USLT:"):
                return str(audio.tags[key])
        for lk in ("lyrics", "LYRICS"):
            val = audio.tags.get(lk)
            if val:
                text = str(val[0]) if isinstance(val, list) else str(val)
                if text.strip():
                    return text
        if "\xa9lyr" in audio.tags:
            return str(audio.tags["\xa9lyr"][0])
    except Exception:
        pass
    return None
