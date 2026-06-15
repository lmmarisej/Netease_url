"""QQ音乐（腾讯音乐）API模块

提供QQ音乐相关接口封装，作为网易云之外的第二音源：
- 音乐搜索
- 歌曲详情
- 歌曲播放/下载URL获取（vkey）
- 歌词获取

接口来源整理见 config/qq_music_api.json。
本模块复用 music_api 中的 SSL 校验策略与会话配置。
"""

import base64
import json
import time
from random import randrange
from typing import Any, Dict, List, Optional

import requests

try:
    # 复用网易云模块统一的会话（含 SSL 校验策略）
    from music_api import _session
except Exception:  # pragma: no cover - 兜底，避免循环导入异常时无法工作
    _session = requests.Session()
    _session.verify = False


class QQAPIException(Exception):
    """QQ音乐API异常类"""
    pass


class QQConstants:
    """QQ音乐API相关常量"""

    USER_AGENT = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    )
    REFERER = 'https://y.qq.com/'
    GUID = '10000'
    UIN = '0'

    MUSICU_API = 'https://u.y.qq.com/cgi-bin/musicu.fcg'
    SMARTBOX_API = 'https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg'
    SONG_INFO_API = 'https://c.y.qq.com/v8/fcg-bin/fcg_play_single_song.fcg'
    VKEY_API = 'https://u.y.qq.com/cgi-bin/musicu.fcg'
    LYRIC_API = 'https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg'
    COVER_TEMPLATE = 'https://y.qq.com/music/photo_new/T002R300x300M000{album_mid}.jpg'

    # 音质等级 -> 文件名前缀(s) / 扩展名(e)
    FILE_CONFIG = {
        '128': {'s': 'M500', 'e': '.mp3'},
        '320': {'s': 'M800', 'e': '.mp3'},
        'flac': {'s': 'F000', 'e': '.flac'},
        'master': {'s': 'AI00', 'e': '.flac'},
    }

    # 由下载请求的统一音质（沿用网易云的命名）映射到QQ音质键
    # 用于跨音源时前端无需区分音质体系
    QUALITY_MAP = {
        'standard': '128',
        'exhigh': '320',
        'lossless': 'flac',
        'hires': 'flac',
        'sky': 'master',
        'jyeffect': 'master',
        'jymaster': 'master',
    }

    # QQ音质降级顺序（从高到低）
    QUALITY_ORDER = ['master', 'flac', '320', '128']


class QQMusicAPI:
    """QQ音乐API主类"""

    def __init__(self, cookie: str = ''):
        """
        Args:
            cookie: QQ音乐登录Cookie字符串（可选）。
                    QQ音乐当前对完整搜索结果与下载链接均需登录态，
                    未提供时搜索退化为联想词(smartbox)，下载多数歌曲会失败。
        """
        self._cookie = (cookie or '').strip()
        self._headers = {
            'User-Agent': QQConstants.USER_AGENT,
            'Referer': QQConstants.REFERER,
        }
        if self._cookie:
            self._headers['Cookie'] = self._cookie

    @property
    def has_cookie(self) -> bool:
        return bool(self._cookie)

    # ------------------------------------------------------------------ #
    # 搜索
    # ------------------------------------------------------------------ #
    def search_music(self, keywords: str, limit: int = 30) -> List[Dict[str, Any]]:
        """搜索QQ音乐歌曲

        优先使用官方桌面端搜索接口（结果丰富，需登录态）；
        当结果为空（通常因未登录）时退化为联想词接口并补全详情。

        Args:
            keywords: 搜索关键词
            limit: 返回数量

        Returns:
            歌曲信息列表，字段与网易云搜索结果对齐：
            id(songmid), name, artists, album, picUrl, source='qq'
        """
        songs = self._search_desktop(keywords, limit)
        if not songs:
            # 未登录或桌面接口不可用时的兜底方案
            songs = self._search_smartbox(keywords, limit)
        return songs

    def _search_desktop(self, keywords: str, limit: int) -> List[Dict[str, Any]]:
        """官方桌面端搜索接口（music.search.SearchCgiService）"""
        data = {
            'comm': {'ct': 24, 'cv': 0},
            'req_1': {
                'module': 'music.search.SearchCgiService',
                'method': 'DoSearchForQQMusicDesktop',
                'param': {
                    'num_per_page': limit,
                    'page_num': 1,
                    'query': keywords,
                    'search_type': 0,
                    'grp': 1,
                },
            },
        }
        try:
            resp = _session.get(QQConstants.MUSICU_API,
                                params={'format': 'json', 'data': json.dumps(data, ensure_ascii=False)},
                                headers=self._headers, timeout=30)
            resp.raise_for_status()
            result = resp.json()
        except (requests.RequestException, json.JSONDecodeError):
            return []

        body = (((result.get('req_1', {}) or {}).get('data', {}) or {}).get('body', {}) or {})
        items = (body.get('song', {}) or {}).get('list', []) or []

        songs: List[Dict[str, Any]] = []
        for item in items:
            songmid = item.get('mid') or item.get('songmid')
            if not songmid:
                continue
            album = item.get('album', {}) or {}
            album_mid = album.get('mid') or item.get('albummid') or ''
            singers = item.get('singer', []) or []
            artists = '/'.join(s.get('name', '') for s in singers if s.get('name'))
            songs.append({
                'id': songmid,
                'name': item.get('name') or item.get('title') or item.get('songname', ''),
                'artists': artists,
                'album': album.get('name') or item.get('albumname', ''),
                'picUrl': QQConstants.COVER_TEMPLATE.format(album_mid=album_mid) if album_mid else '',
                'source': 'qq',
                'songid': item.get('id') or item.get('songid'),
                'album_mid': album_mid,
            })
        return songs

    def _search_smartbox(self, keywords: str, limit: int) -> List[Dict[str, Any]]:
        """联想词接口兜底搜索，并补全专辑/封面信息"""
        try:
            resp = _session.get(QQConstants.SMARTBOX_API,
                                params={'key': keywords, 'format': 'json'},
                                headers=self._headers, timeout=30)
            resp.raise_for_status()
            result = resp.json()
        except (requests.RequestException, json.JSONDecodeError):
            return []

        itemlist = (((result.get('data', {}) or {}).get('song', {}) or {}).get('itemlist', []) or [])
        songs: List[Dict[str, Any]] = []
        for item in itemlist[:limit]:
            songmid = item.get('mid')
            if not songmid:
                continue
            song = {
                'id': songmid,
                'name': item.get('name', ''),
                'artists': item.get('singer', ''),
                'album': '',
                'picUrl': '',
                'source': 'qq',
                'songid': item.get('id'),
                'album_mid': '',
            }
            # 联想词接口缺少专辑/封面，逐条补全（数量很少，开销可控）
            try:
                detail = self.get_song_detail(songmid)
                song['album'] = detail.get('album', '')
                song['album_mid'] = detail.get('album_mid', '')
                song['picUrl'] = detail.get('picUrl', '')
                if detail.get('artists'):
                    song['artists'] = detail['artists']
            except QQAPIException:
                pass
            songs.append(song)
        return songs

    # ------------------------------------------------------------------ #
    # 歌曲详情
    # ------------------------------------------------------------------ #
    def get_song_detail(self, songmid: str) -> Dict[str, Any]:
        """由 songmid 获取歌曲详情"""
        params = {'songmid': songmid, 'platform': 'yqq', 'format': 'json'}
        try:
            resp = _session.get(QQConstants.SONG_INFO_API, params=params,
                                headers=self._headers, timeout=30)
            resp.raise_for_status()
            result = resp.json()
        except requests.RequestException as e:
            raise QQAPIException(f"获取QQ音乐歌曲详情请求失败: {e}")
        except json.JSONDecodeError as e:
            raise QQAPIException(f"解析QQ音乐歌曲详情失败: {e}")

        data = result.get('data', [])
        if not data:
            raise QQAPIException("未找到该QQ音乐歌曲信息")

        info = data[0]
        album_info = info.get('album', {}) or {}
        album_mid = album_info.get('mid', '')
        singers = info.get('singer', []) or []
        return {
            'id': info.get('mid', songmid),
            'songid': info.get('id'),
            'name': info.get('name', ''),
            'artists': '/'.join(s.get('name', '') for s in singers if s.get('name')),
            'album': album_info.get('name', ''),
            'album_mid': album_mid,
            'picUrl': QQConstants.COVER_TEMPLATE.format(album_mid=album_mid) if album_mid else '',
            'interval': info.get('interval', 0),
            'source': 'qq',
        }

    # ------------------------------------------------------------------ #
    # 播放/下载URL
    # ------------------------------------------------------------------ #
    def get_song_url(self, songmid: str, quality: str = 'flac') -> Dict[str, Any]:
        """获取歌曲真实播放/下载地址

        Args:
            songmid: QQ音乐 songmid
            quality: QQ音质键（128/320/flac/master）

        Returns:
            {'url': 直链, 'quality': 实际音质, 'ext': 扩展名}
            若所有音质均不可用，url 为 None
        """
        if quality not in QQConstants.FILE_CONFIG:
            quality = 'flac'

        # 从请求音质开始逐级降级
        try:
            start_idx = QQConstants.QUALITY_ORDER.index(quality)
        except ValueError:
            start_idx = QQConstants.QUALITY_ORDER.index('flac')

        for q in QQConstants.QUALITY_ORDER[start_idx:]:
            cfg = QQConstants.FILE_CONFIG[q]
            filename = f"{cfg['s']}{songmid}{songmid}{cfg['e']}"
            url = self._request_vkey(songmid, filename)
            if url:
                return {'url': url, 'quality': q, 'ext': cfg['e']}

        return {'url': None, 'quality': quality, 'ext': QQConstants.FILE_CONFIG[quality]['e']}

    def _request_vkey(self, songmid: str, filename: str) -> Optional[str]:
        """请求 vkey 并拼接最终URL，失败/无权限返回 None

        使用登录态Cookie中的 uin（若存在），否则使用游客 uin=0。
        """
        uin = self._uin_from_cookie() or QQConstants.UIN
        guid = QQConstants.GUID
        data = {
            'req': {
                'module': 'CDN.SrfCdnDispatchServer',
                'method': 'GetCdnDispatch',
                'param': {'guid': guid, 'calltype': 0, 'userip': ''},
            },
            'req_0': {
                'module': 'vkey.GetVkeyServer',
                'method': 'CgiGetVkey',
                'param': {
                    'filename': [filename],
                    'guid': guid,
                    'songmid': [songmid],
                    'songtype': [0],
                    'uin': uin,
                    'loginflag': 1,
                    'platform': '20',
                },
            },
            'loginUin': uin,
            'comm': {'uin': uin, 'format': 'json', 'ct': 24, 'cv': 0},
        }
        params = {
            'format': 'json',
            'platform': 'yqq.json',
            'needNewCode': 0,
            'data': json.dumps(data, ensure_ascii=False),
        }
        try:
            resp = _session.get(QQConstants.VKEY_API, params=params,
                                headers=self._headers, timeout=30)
            resp.raise_for_status()
            result = resp.json()
        except (requests.RequestException, json.JSONDecodeError):
            return None

        req_data = (result.get('req_0', {}) or {}).get('data', {}) or {}
        midurlinfo = req_data.get('midurlinfo', []) or []
        if not midurlinfo:
            return None
        purl = midurlinfo[0].get('purl')
        if not purl:
            # purl 为空 -> 需登录 / VIP / 无版权 / 该音质不可用
            return None
        sips = req_data.get('sip', []) or []
        sip = sips[0] if sips else 'https://dl.stream.qqmusic.qq.com/'
        final_url = sip + purl
        return final_url.replace('http://', 'https://')

    def _uin_from_cookie(self) -> str:
        """从Cookie中提取 uin（qqmusic_uin / uin / wxuin），失败返回空串"""
        if not self._cookie:
            return ''
        try:
            parts = dict(
                p.strip().split('=', 1) for p in self._cookie.split(';') if '=' in p
            )
        except Exception:
            return ''
        for key in ('qqmusic_uin', 'uin', 'wxuin', 'euin'):
            val = parts.get(key, '').strip()
            if val:
                return ''.join(ch for ch in val if ch.isdigit()) or val
        return ''

    # ------------------------------------------------------------------ #
    # 歌词
    # ------------------------------------------------------------------ #
    def get_lyric(self, songmid: str) -> str:
        """由 songmid 获取歌词（已 base64 解码的纯文本）"""
        params = {
            '_': int(time.time() * 1000),
            'format': 'json',
            'loginUin': randrange(1000000000, 9999999999),
            'songmid': songmid,
        }
        try:
            resp = _session.get(QQConstants.LYRIC_API, params=params,
                                headers=self._headers, timeout=30)
            resp.raise_for_status()
            result = resp.json()
        except (requests.RequestException, json.JSONDecodeError):
            return ''

        raw = result.get('lyric', '')
        if not raw:
            return ''
        try:
            return base64.b64decode(raw).decode('utf-8', errors='ignore')
        except Exception:
            return raw


# ---------------------------------------------------------------------- #
# 向后兼容的模块级函数
# ---------------------------------------------------------------------- #
def qq_search_music(keywords: str, limit: int = 30, cookie: str = '') -> List[Dict[str, Any]]:
    """搜索QQ音乐（模块级快捷函数）"""
    return QQMusicAPI(cookie).search_music(keywords, limit)


def qq_song_detail(songmid: str, cookie: str = '') -> Dict[str, Any]:
    """获取QQ音乐歌曲详情（模块级快捷函数）"""
    return QQMusicAPI(cookie).get_song_detail(songmid)


def qq_song_url(songmid: str, quality: str = 'flac', cookie: str = '') -> Dict[str, Any]:
    """获取QQ音乐下载地址（模块级快捷函数）"""
    return QQMusicAPI(cookie).get_song_url(songmid, quality)


def qq_lyric(songmid: str, cookie: str = '') -> str:
    """获取QQ音乐歌词（模块级快捷函数）"""
    return QQMusicAPI(cookie).get_lyric(songmid)


def map_quality_to_qq(quality: str) -> str:
    """将统一音质命名映射到QQ音质键"""
    return QQConstants.QUALITY_MAP.get(quality, 'flac')
