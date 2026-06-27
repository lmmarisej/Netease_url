"""
AudioAnalysisEngine — 音频分析引擎门面

职责：统一封装多模型（Librosa、Demucs、PANNs、Ollama）的调用入口。
Service 层只通过此门面调用特征计算，不直接接触具体模型。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("audio_engine")


class AudioAnalysisEngine:
    """
    音频分析计算引擎 — 统一门面。

    当前实现直接委托到 music_processor 的现有模块，
    后续可按需替换为独立计算服务/GPU集群调度。
    """

    def __init__(self):
        pass

    # ── Librosa 声学特征 ──

    def extract_librosa_features(self, file_path: str) -> Dict[str, Any]:
        """
        提取 5 维 librosa 声学特征 (tempo, energy, brightness,
        energy_contrast, tonality) + 节奏 (rhythm)。
        """
        from music_processor.features import extract_features
        return extract_features(file_path) or {}

    # ── Demucs 人声/低音分离 ──

    def extract_demucs_scores(self, file_path: str) -> Dict[str, int]:
        """提取 vocal_dominant 和 sub_bass 评分（异步提交到后台线程）"""
        try:
            from music_processor.demucs import analyze_demucs_async
            analyze_demucs_async(file_path)  # fire-and-forget
            return {"score_vocal_dominant": 0, "score_sub_bass": 0}
        except Exception as e:
            logger.warning(f"Demucs 分析失败: {e}")
            return {"score_vocal_dominant": 0, "score_sub_bass": 0}

    # ── PANNs 音频标签 ──

    def extract_panns_tags(self, file_path: str) -> List[Dict[str, Any]]:
        """提取 PANNs CNN14 音频标签"""
        try:
            from music_processor.panns import extract_panns_tags
            return extract_panns_tags(file_path) or []
        except ImportError:
            logger.warning("panns-inference 未安装，跳过")
            return []

    # ── Ollama LLM 歌词意境 ──

    def analyze_lyrics_llm(self, lyrics_text: str) -> List[str]:
        """调用本地 Ollama qwen2:1.5b 分析歌词意境标签"""
        try:
            from music_processor.llm import analyze_lyrics_via_llm
            return analyze_lyrics_via_llm(lyrics_text)
        except Exception as e:
            logger.warning(f"LLM 分析失败: {e}")
            return []

    # ── SnowNLP 情感 ──

    def score_lyric_sentiment(self, lyrics_text: str) -> int:
        """SnowNLP 歌词情感评分 (0-100)"""
        try:
            from music_processor.sentiment import score_lyric_sentiment
            return score_lyric_sentiment(lyrics_text)
        except ImportError:
            return 50  # 默认中性

    # ── 元数据 ──

    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """提取歌曲元数据（title, artist, album, lyrics）"""
        try:
            from music_processor.metadata import extract_metadata as _meta
            return _meta(file_path) or {}
        except Exception as e:
            logger.warning(f"元数据提取失败: {e}")
            return {}
