"""snownlp 歌词情感分析。"""


def score_lyric_sentiment(lyrics: str | None) -> int:
    """SnowNLP 情感分析 → 0-100（悲伤→快乐），无歌词兜底 50。"""
    if not lyrics or not lyrics.strip():
        return 50
    try:
        from snownlp import SnowNLP
    except ImportError:
        return 50
    try:
        return int(round(SnowNLP(lyrics).sentiments * 100))
    except Exception:
        return 50
