"""网易云音乐API模块

提供网易云音乐相关API接口的封装，包括：
- 音乐URL获取
- 歌曲详情获取
- 歌词获取
- 搜索功能
- 歌单和专辑详情
- 二维码登录
- 歌曲喜欢/取消喜欢（红心）
- 获取用户喜欢列表
"""

import base64
import json
import os
import urllib.parse
import time
from random import randrange
from typing import Dict, List, Optional, Tuple, Any
from hashlib import md5
from enum import Enum

import requests
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import padding as _asym_padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.backends import default_backend


def _resolve_ssl_verify():
    """解析 SSL 校验策略

    默认关闭校验（内网代理拦截 HTTPS 场景；存在中间人风险，请确保可信内网）。

    环境变量：
        NETEASE_SSL_VERIFY=1/true/yes/on   -> 重新开启校验
        NETEASE_SSL_VERIFY=0/false/no/off  -> 关闭校验（默认）
        NETEASE_CA_BUNDLE / REQUESTS_CA_BUNDLE=<path>  -> 指定企业根证书（推荐，保持安全）
    """
    flag = os.environ.get('NETEASE_SSL_VERIFY', '').strip().lower()
    ca_bundle = os.environ.get('NETEASE_CA_BUNDLE') or os.environ.get('REQUESTS_CA_BUNDLE')

    if flag in ('1', 'true', 'yes', 'on'):
        if ca_bundle and os.path.exists(ca_bundle):
            return ca_bundle
        return True
    if flag in ('0', 'false', 'no', 'off'):
        return False

    # 未显式设置：若提供了企业根证书则用之（安全），否则默认关闭校验
    if ca_bundle and os.path.exists(ca_bundle):
        return ca_bundle
    return False


SSL_VERIFY = _resolve_ssl_verify()

# 统一外部请求会话：集中管理 SSL 校验策略
_session = requests.Session()
_session.verify = SSL_VERIFY

if SSL_VERIFY is False:
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass


class QualityLevel(Enum):
    """音质等级枚举"""
    STANDARD = "standard"      # 标准音质
    HIGHER = "higher"          # 较高音质
    EXHIGH = "exhigh"          # 极高音质
    LOSSLESS = "lossless"      # 无损音质
    HIRES = "hires"            # Hi-Res音质
    SKY = "sky"                # 沉浸环绕声
    JYEFFECT = "jyeffect"      # 高清环绕声
    JYMASTER = "jymaster"      # 超清母带
    DOLBY = "dolby"            # 杜比全景声


# 常量定义
class APIConstants:
    """API相关常量"""
    AES_KEY = b"e82ckenh8dichen8"
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36 Chrome/91.0.4472.164 NeteaseMusicDesktop/2.10.2.200154'
    REFERER = 'https://music.163.com/'
    
    # API URLs
    SONG_URL_V1 = "https://interface3.music.163.com/eapi/song/enhance/player/url/v1"
    SONG_DOWNLOAD_URL_V1 = "https://interface3.music.163.com/eapi/song/download/url/v1"
    SONG_DETAIL_V3 = "https://interface3.music.163.com/api/v3/song/detail"
    LYRIC_API = "https://interface3.music.163.com/api/song/lyric"
    SEARCH_API = 'https://music.163.com/api/cloudsearch/pc'
    PLAYLIST_DETAIL_API = 'https://music.163.com/api/v6/playlist/detail'
    ALBUM_DETAIL_API = 'https://music.163.com/api/v1/album/'
    QR_UNIKEY_API = 'https://interface3.music.163.com/eapi/login/qrcode/unikey'
    QR_LOGIN_API = 'https://interface3.music.163.com/eapi/login/qrcode/client/login'
    RADIO_LIKE_API = 'https://music.163.com/weapi/radio/like'
    LIKE_LIST_API = 'https://music.163.com/weapi/song/like/get'
    USER_ACCOUNT_API = 'https://music.163.com/api/nuser/account/get'
    USER_PLAYLIST_API = 'https://music.163.com/api/user/playlist'
    PLAYLIST_MANIPULATE_API = 'https://music.163.com/api/playlist/manipulate/tracks'

    # 默认配置
    DEFAULT_CONFIG = {
        "os": "pc",
        "appver": "",
        "osver": "",
        "deviceId": "pyncm!"
    }
    
    DEFAULT_COOKIES = {
        "os": "pc",
        "appver": "",
        "osver": "",
        "deviceId": "pyncm!"
    }


# ── RSA 公钥常量（weapi 加密用） ──
_RSA_MODULUS_HEX = (
    "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b7"
    "25152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e"
    "0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce"
    "10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462"
    "db0a22b8e7"
)
_RSA_MODULUS = int(_RSA_MODULUS_HEX, 16)
_RSA_EXPONENT = 65537
_RSA_KEY = RSAPublicNumbers(_RSA_EXPONENT, _RSA_MODULUS).public_key(default_backend())
_WEAPI_NONCE = "0CoJUm6Qyw8W8jud"
_WEAPI_IV = "0102030405060708"


class CryptoUtils:
    """加密工具类"""

    @staticmethod
    def hex_digest(data: bytes) -> str:
        """将字节数据转换为十六进制字符串"""
        return "".join([hex(d)[2:].zfill(2) for d in data])

    @staticmethod
    def hash_digest(text: str) -> bytes:
        """计算MD5哈希值"""
        return md5(text.encode("utf-8")).digest()

    @staticmethod
    def hash_hex_digest(text: str) -> str:
        """计算MD5哈希值并转换为十六进制字符串"""
        return CryptoUtils.hex_digest(CryptoUtils.hash_digest(text))

    @staticmethod
    def encrypt_params(url: str, payload: Dict[str, Any]) -> str:
        """eapi 加密请求参数（用于 /eapi/* 接口）"""
        url_path = urllib.parse.urlparse(url).path.replace("/eapi/", "/api/")
        digest = CryptoUtils.hash_hex_digest(f"nobody{url_path}use{json.dumps(payload)}md5forencrypt")
        params = f"{url_path}-36cd479b6b5-{json.dumps(payload)}-36cd479b6b5-{digest}"

        # AES-ECB 加密
        padder = padding.PKCS7(algorithms.AES(APIConstants.AES_KEY).block_size).padder()
        padded_data = padder.update(params.encode()) + padder.finalize()
        cipher = Cipher(algorithms.AES(APIConstants.AES_KEY), modes.ECB())
        encryptor = cipher.encryptor()
        enc = encryptor.update(padded_data) + encryptor.finalize()

        return CryptoUtils.hex_digest(enc)

    # ── weapi 加密（用于 /weapi/* 接口，如喜欢/取消喜欢） ──

    @staticmethod
    def _aes_encrypt_cbc(text: str, key: str) -> str:
        """AES-128-CBC 加密，Base64 输出"""
        padder = padding.PKCS7(128).padder()
        padded = padder.update(text.encode("utf-8")) + padder.finalize()
        cipher = Cipher(algorithms.AES(key.encode("utf-8")), modes.CBC(_WEAPI_IV.encode("utf-8")))
        encryptor = cipher.encryptor()
        enc = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(enc).decode("utf-8")

    @staticmethod
    def _rsa_encrypt(text: str) -> str:
        """RSA-1024 加密（PKCS1v15 填充），Base64 输出"""
        encrypted = _RSA_KEY.encrypt(text[::-1].encode("utf-8"), _asym_padding.PKCS1v15())
        return base64.b64encode(encrypted).decode("utf-8")

    @staticmethod
    def weapi_encrypt_params(payload: Dict[str, Any]) -> str:
        """weapi 加密请求参数，返回 URL-encoded form data 字符串

        两层 AES-CBC：先用固定 NONCE 加密，再用随机密钥加密。
        encSecKey 用 RSA 公钥加密反转后的随机密钥。

        Returns:
            "params=...&encSecKey=..." 格式的 form data 字符串
        """
        text = json.dumps(payload)
        # 生成随机密钥（8 bytes → 16 hex chars = 128 bit）
        secret_key = base64.b16encode(os.urandom(8)).decode("utf-8").lower()
        # 两层加密
        params = CryptoUtils._aes_encrypt_cbc(
            CryptoUtils._aes_encrypt_cbc(text, _WEAPI_NONCE),
            secret_key,
        )
        enc_sec_key = CryptoUtils._rsa_encrypt(secret_key)
        return f"params={urllib.parse.quote(params)}&encSecKey={urllib.parse.quote(enc_sec_key)}"


class HTTPClient:
    """HTTP客户端类"""

    @staticmethod
    def post_request(url: str, params: str, cookies: Dict[str, str]) -> str:
        """发送 eapi POST 请求并返回文本响应"""
        headers = {
            'User-Agent': APIConstants.USER_AGENT,
            'Referer': APIConstants.REFERER,
        }

        request_cookies = APIConstants.DEFAULT_COOKIES.copy()
        request_cookies.update(cookies)

        try:
            response = _session.post(url, headers=headers, cookies=request_cookies,
                                   data={"params": params}, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            raise APIException(f"HTTP请求失败: {e}")

    @staticmethod
    def post_request_full(url: str, params: str, cookies: Dict[str, str]) -> requests.Response:
        """发送 eapi POST 请求并返回完整响应对象"""
        headers = {
            'User-Agent': APIConstants.USER_AGENT,
            'Referer': APIConstants.REFERER,
        }

        request_cookies = APIConstants.DEFAULT_COOKIES.copy()
        request_cookies.update(cookies)

        try:
            response = _session.post(url, headers=headers, cookies=request_cookies,
                                   data={"params": params}, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            raise APIException(f"HTTP请求失败: {e}")

    @staticmethod
    def post_weapi_request(url: str, payload: Dict[str, Any], cookies: Dict[str, str]) -> str:
        """发送 weapi POST 请求并返回文本响应

        用于 /weapi/* 接口（如喜欢/取消喜欢、获取喜欢列表等）。
        body 为 URL-encoded form data: params=...&encSecKey=...
        """
        form_data = CryptoUtils.weapi_encrypt_params(payload)
        headers = {
            'User-Agent': APIConstants.USER_AGENT,
            'Referer': APIConstants.REFERER,
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        request_cookies = APIConstants.DEFAULT_COOKIES.copy()
        request_cookies.update(cookies)

        try:
            response = _session.post(url, headers=headers, cookies=request_cookies,
                                   data=form_data, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            raise APIException(f"HTTP请求失败: {e}")


class APIException(Exception):
    """API异常类"""
    pass


class NeteaseAPI:
    """网易云音乐API主类"""
    
    def __init__(self):
        self.http_client = HTTPClient()
        self.crypto_utils = CryptoUtils()
    
    def get_song_url(self, song_id: int, quality: str, cookies: Dict[str, str]) -> Dict[str, Any]:
        """获取歌曲播放URL
        
        Args:
            song_id: 歌曲ID
            quality: 音质等级 (standard, exhigh, lossless, hires, sky, jyeffect, jymaster)
            cookies: 用户cookies
            
        Returns:
            包含歌曲URL信息的字典
            
        Raises:
            APIException: API调用失败时抛出
        """
        try:
            config = APIConstants.DEFAULT_CONFIG.copy()
            config["requestId"] = str(randrange(20000000, 30000000))
            
            payload = {
                'ids': [song_id],
                'level': quality,
                'encodeType': 'flac',
                'header': json.dumps(config),
            }
            
            if quality == 'sky':
                payload['immerseType'] = 'c51'
            
            params = self.crypto_utils.encrypt_params(APIConstants.SONG_URL_V1, payload)
            response_text = self.http_client.post_request(APIConstants.SONG_URL_V1, params, cookies)
            
            result = json.loads(response_text)
            if result.get('code') != 200:
                raise APIException(f"获取歌曲URL失败: {result.get('message', '未知错误')}")
            
            return result
        except (json.JSONDecodeError, KeyError) as e:
            raise APIException(f"解析响应数据失败: {e}")
    
    def get_song_download_url(self, song_id: int, quality: str, cookies: Dict[str, str]) -> Dict[str, Any]:
        """获取歌曲下载URL（新版 /song/download/url/v1）
        
        与旧版 /song/enhance/player/url/v1 的区别：
        - 旧版是试听链接，非VIP只能获取标准/极高音质
        - 新版是下载链接，免费歌曲(fee==0)可获取Hi-Res，VIP歌曲可获取无损
        
        Args:
            song_id: 歌曲ID
            quality: 音质等级 (standard, higher, exhigh, lossless, hires, sky, jyeffect, jymaster, dolby)
            cookies: 用户cookies
            
        Returns:
            包含歌曲下载URL信息的字典
            
        Raises:
            APIException: API调用失败时抛出
        """
        try:
            payload = {
                'id': song_id,
                'level': quality,
            }
            
            params = self.crypto_utils.encrypt_params(APIConstants.SONG_DOWNLOAD_URL_V1, payload)
            response_text = self.http_client.post_request(APIConstants.SONG_DOWNLOAD_URL_V1, params, cookies)
            
            result = json.loads(response_text)
            if result.get('code') != 200:
                raise APIException(f"获取歌曲下载URL失败: {result.get('message', '未知错误')}")
            
            # 归一化格式：新接口返回 {"data": {...}}，转为旧接口兼容的 {"data": [{...}]}
            if result.get('data') and not isinstance(result.get('data'), list):
                result['data'] = [result['data']]
            
            return result
        except (json.JSONDecodeError, KeyError) as e:
            raise APIException(f"解析下载响应数据失败: {e}")
    
    def get_song_detail(self, song_id: int) -> Dict[str, Any]:
        """获取歌曲详细信息
        
        Args:
            song_id: 歌曲ID
            
        Returns:
            包含歌曲详细信息的字典
            
        Raises:
            APIException: API调用失败时抛出
        """
        try:
            data = {'c': json.dumps([{"id": song_id, "v": 0}])}
            response = _session.post(APIConstants.SONG_DETAIL_V3, data=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') != 200:
                raise APIException(f"获取歌曲详情失败: {result.get('message', '未知错误')}")
            
            return result
        except requests.RequestException as e:
            raise APIException(f"获取歌曲详情请求失败: {e}")
        except json.JSONDecodeError as e:
            raise APIException(f"解析歌曲详情响应失败: {e}")
    
    def get_songs_detail_batch(self, song_ids: list, cookies: Dict[str, str] = None) -> list:
        """批量获取多首歌曲详情（用于喜欢列表等场景）

        API: POST https://interface3.music.163.com/api/v3/song/detail
        一次请求最多传约 1000 个 ID。

        Returns:
            歌曲列表 [{id, name, ar: [{name}], al: {name, picUrl}}, ...]
        """
        results = []
        chunk_size = 500
        for i in range(0, len(song_ids), chunk_size):
            chunk = song_ids[i:i + chunk_size]
            try:
                c_data = [{"id": int(sid)} for sid in chunk]
                data = {'c': json.dumps(c_data)}
                resp = _session.post(APIConstants.SONG_DETAIL_V3, data=data, timeout=30)
                resp.raise_for_status()
                result = resp.json()
                if result.get('code') == 200 and result.get('songs'):
                    results.extend(result['songs'])
            except Exception:
                continue
        return results
    
    def get_lyric(self, song_id: int, cookies: Dict[str, str]) -> Dict[str, Any]:
        """获取歌词信息
        
        Args:
            song_id: 歌曲ID
            cookies: 用户cookies
            
        Returns:
            包含歌词信息的字典
            
        Raises:
            APIException: API调用失败时抛出
        """
        try:
            data = {
                'id': song_id, 
                'cp': 'false', 
                'tv': '0', 
                'lv': '0', 
                'rv': '0', 
                'kv': '0', 
                'yv': '0', 
                'ytv': '0', 
                'yrv': '0'
            }
            
            headers = {
                'User-Agent': APIConstants.USER_AGENT,
                'Referer': APIConstants.REFERER
            }
            
            response = _session.post(APIConstants.LYRIC_API, data=data, 
                                   headers=headers, cookies=cookies, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') != 200:
                raise APIException(f"获取歌词失败: {result.get('message', '未知错误')}")
            
            return result
        except requests.RequestException as e:
            raise APIException(f"获取歌词请求失败: {e}")
        except json.JSONDecodeError as e:
            raise APIException(f"解析歌词响应失败: {e}")
    
    def search_music(self, keywords: str, cookies: Dict[str, str], limit: int = 10) -> List[Dict[str, Any]]:
        """搜索音乐
        
        Args:
            keywords: 搜索关键词
            cookies: 用户cookies
            limit: 返回数量限制
            
        Returns:
            歌曲信息列表
            
        Raises:
            APIException: API调用失败时抛出
        """
        try:
            data = {'s': keywords, 'type': 1, 'limit': limit}
            headers = {
                'User-Agent': APIConstants.USER_AGENT,
                'Referer': APIConstants.REFERER
            }
            
            response = _session.post(APIConstants.SEARCH_API, data=data, 
                                   headers=headers, cookies=cookies, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') != 200:
                raise APIException(f"搜索失败: {result.get('message', '未知错误')}")
            
            songs = []
            for item in result.get('result', {}).get('songs', []):
                song_info = {
                    'id': item['id'],
                    'name': item['name'],
                    'artists': '/'.join(artist['name'] for artist in item['ar']),
                    'album': item['al']['name'],
                    'picUrl': item['al']['picUrl']
                }
                songs.append(song_info)
            
            return songs
        except requests.RequestException as e:
            raise APIException(f"搜索请求失败: {e}")
        except (json.JSONDecodeError, KeyError) as e:
            raise APIException(f"解析搜索响应失败: {e}")
    
    def get_playlist_detail(self, playlist_id: int, cookies: Dict[str, str]) -> Dict[str, Any]:
        """获取歌单详情

        API: GET https://music.163.com/api/v6/playlist/detail?id=xxx

        Args:
            playlist_id: 歌单ID
            cookies: 用户cookies

        Returns:
            歌单详情，包含 tracks 数组（每项含 id/name/ar/al）
        """
        try:
            headers = {
                'User-Agent': APIConstants.USER_AGENT,
                'Referer': APIConstants.REFERER,
            }
            url = f"{APIConstants.PLAYLIST_DETAIL_API}?id={playlist_id}"
            response = _session.get(url, headers=headers, cookies=cookies, timeout=30)
            response.raise_for_status()
            result = response.json()
            if result.get('code') != 200:
                raise APIException(f"获取歌单详情失败: {result.get('message', '未知错误')}")
            playlist = result.get('playlist', {})
            tracks = playlist.get('tracks', [])
            track_ids = [str(t['id']) for t in playlist.get('trackIds', [])]
            # 若返回的 tracks 不完整（API 默认只返回前 ~10 首），用 trackIds 批量补齐
            if track_ids and len(tracks) < playlist.get('trackCount', 0):
                tracks_map = {str(t['id']): t for t in tracks}
                for i in range(0, len(track_ids), 500):
                    batch_ids = [int(sid) for sid in track_ids[i:i + 500] if sid not in tracks_map]
                    if not batch_ids:
                        continue
                    song_data = {'c': json.dumps([{'id': sid} for sid in batch_ids])}
                    song_resp = _session.post(
                        APIConstants.SONG_DETAIL_V3, data=song_data,
                        headers=headers, cookies=cookies, timeout=30,
                    )
                    song_resp.raise_for_status()
                    songs = song_resp.json().get('songs', [])
                    tracks.extend(songs)
            return {
                'id': playlist.get('id'),
                'name': playlist.get('name'),
                'trackCount': playlist.get('trackCount'),
                'tracks': tracks,
            }
        except requests.RequestException as e:
            raise APIException(f"获取歌单详情请求失败: {e}")
        except (json.JSONDecodeError, KeyError) as e:
            raise APIException(f"解析歌单详情响应失败: {e}")
    
    def get_album_detail(self, album_id: int, cookies: Dict[str, str]) -> Dict[str, Any]:
        """获取专辑详情
        
        Args:
            album_id: 专辑ID
            cookies: 用户cookies
            
        Returns:
            专辑详情信息
            
        Raises:
            APIException: API调用失败时抛出
        """
        try:
            url = f'{APIConstants.ALBUM_DETAIL_API}{album_id}'
            headers = {
                'User-Agent': APIConstants.USER_AGENT,
                'Referer': APIConstants.REFERER
            }
            
            response = _session.get(url, headers=headers, cookies=cookies, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') != 200:
                raise APIException(f"获取专辑详情失败: {result.get('message', '未知错误')}")
            
            album = result.get('album', {})
            info = {
                'id': album.get('id'),
                'name': album.get('name'),
                'coverImgUrl': self.get_pic_url(album.get('pic')),
                'artist': album.get('artist', {}).get('name', ''),
                'publishTime': album.get('publishTime'),
                'description': album.get('description', ''),
                'songs': []
            }
            
            for song in result.get('songs', []):
                info['songs'].append({
                    'id': song['id'],
                    'name': song['name'],
                    'artists': '/'.join(artist['name'] for artist in song['ar']),
                    'album': song['al']['name'],
                    'picUrl': self.get_pic_url(song['al'].get('pic'))
                })
            
            return info
        except requests.RequestException as e:
            raise APIException(f"获取专辑详情请求失败: {e}")
        except (json.JSONDecodeError, KeyError) as e:
            raise APIException(f"解析专辑详情响应失败: {e}")
    
    def netease_encrypt_id(self, id_str: str) -> str:
        """网易云加密图片ID算法
        
        Args:
            id_str: 图片ID字符串
            
        Returns:
            加密后的字符串
        """
        import base64
        import hashlib
        
        magic = list('3go8&$8*3*3h0k(2)2')
        song_id = list(id_str)
        
        for i in range(len(song_id)):
            song_id[i] = chr(ord(song_id[i]) ^ ord(magic[i % len(magic)]))
        
        m = ''.join(song_id)
        md5_bytes = hashlib.md5(m.encode('utf-8')).digest()
        result = base64.b64encode(md5_bytes).decode('utf-8')
        result = result.replace('/', '_').replace('+', '-')
        
        return result
    
    def get_pic_url(self, pic_id: Optional[int], size: int = 300) -> str:
        """获取网易云加密歌曲/专辑封面直链
        
        Args:
            pic_id: 封面ID
            size: 图片尺寸
            
        Returns:
            图片URL
        """
        if pic_id is None:
            return ''
        
        enc_id = self.netease_encrypt_id(str(pic_id))
        return f'https://p3.music.126.net/{enc_id}/{pic_id}.jpg?param={size}y{size}'

    # ── 喜欢 / 取消喜欢 ──

    def set_like(self, track_id: int, like: bool, cookies: Dict[str, str]) -> Dict[str, Any]:
        """红心或取消红心歌曲（与网易云官方客户端同步）

        API: POST https://music.163.com/eapi/radio/like (eapi 加密)

        Args:
            track_id: 网易云歌曲ID
            like: True=红心喜欢, False=取消红心
            cookies: 用户cookies（需包含 MUSIC_U 等认证字段）

        Returns:
            API 响应字典，code==200 表示操作成功
        """
        payload = {
            'alg': 'itembased',
            'trackId': track_id,
            'like': like,
            'time': '3',
        }
        cookies_copy = dict(cookies)
        cookies_copy.setdefault('os', 'pc')
        cookies_copy.setdefault('appver', '2.10.15')
        cookies_copy.setdefault('channel', 'netease')

        eapi_params = self.crypto_utils.encrypt_params(
            'https://music.163.com/eapi/radio/like', payload
        )
        response_text = self.http_client.post_request(
            'https://music.163.com/eapi/radio/like', eapi_params, cookies_copy
        )
        result = json.loads(response_text)
        if result.get('code') != 200:
            raise APIException(f"喜欢操作失败: {result.get('message', '未知错误')} (code={result.get('code')})")
        return result

    def get_likelist(self, uid: int, cookies: Dict[str, str]) -> Dict[str, Any]:
        """获取用户喜欢的歌曲列表（无序）

        API: POST https://music.163.com/weapi/song/like/get

        Args:
            uid: 网易云用户ID
            cookies: 用户cookies

        Returns:
            API 响应字典，包含 songIds 等字段
        """
        payload = {'uid': uid}
        response_text = self.http_client.post_weapi_request(
            APIConstants.LIKE_LIST_API, payload, cookies
        )
        result = json.loads(response_text)
        if result.get('code') != 200:
            raise APIException(f"获取喜欢列表失败: {result.get('message', '未知错误')}")
        return result

    def get_user_account(self, cookies: Dict[str, str]) -> Dict[str, Any]:
        """获取当前登录用户的账号信息（无需知道 uid）

        API: POST https://music.163.com/api/nuser/account/get

        Args:
            cookies: 用户cookies

        Returns:
            API 响应字典，包含 account.id（用户ID）、profile（昵称/头像）等
        """
        response_text = self.http_client.post_weapi_request(
            APIConstants.USER_ACCOUNT_API, {}, cookies
        )
        result = json.loads(response_text)
        if result.get('code') != 200:
            raise APIException(f"获取用户账号失败: {result.get('message', '未知错误')}")
        return result

    def get_user_playlist(
        self, uid: int, cookies: Dict[str, str],
        limit: int = 30, offset: int = 0,
    ) -> Dict[str, Any]:
        """获取用户歌单列表（包含创建和收藏的歌单）

        API: GET https://music.163.com/api/user/playlist?uid=xxx&limit=xxx

        返回的 playlist 数组中，specialType=5 的是「我喜欢的音乐」。

        Args:
            uid: 网易云用户ID
            cookies: 用户cookies
            limit: 返回数量
            offset: 偏移量

        Returns:
            API 响应字典，包含 playlist 数组
        """
        url = f"{APIConstants.USER_PLAYLIST_API}?uid={uid}&limit={limit}&offset={offset}"
        headers = {
            'User-Agent': APIConstants.USER_AGENT,
            'Referer': APIConstants.REFERER,
        }
        try:
            response = _session.get(url, headers=headers, cookies=cookies, timeout=30)
            response.raise_for_status()
            result = response.json()
            if result.get('code') != 200:
                raise APIException(f"获取用户歌单失败: {result.get('message', '未知错误')}")
            return result
        except requests.RequestException as e:
            raise APIException(f"获取用户歌单请求失败: {e}")

    def manipulate_playlist_tracks(
        self, pid: int, track_ids: List[int], op: str, cookies: Dict[str, str]
    ) -> Dict[str, Any]:
        """向歌单添加/删除歌曲（通用歌单操作）

        API: POST https://music.163.com/api/playlist/manipulate/tracks

        用于操作「我喜欢的音乐」等任意歌单：op='add' 添加，op='del' 删除。

        Args:
            pid: 歌单ID（如「我喜欢的音乐」的ID）
            track_ids: 歌曲ID列表
            op: 'add' 添加歌曲 / 'del' 删除歌曲
            cookies: 用户cookies（需 os='pc'）

        Returns:
            API 响应字典
        """
        cookies_copy = dict(cookies)
        cookies_copy.setdefault('os', 'pc')
        payload = {
            'op': op,
            'pid': pid,
            'trackIds': json.dumps([str(tid) for tid in track_ids]),
            'imme': 'true',
        }
        response_text = self.http_client.post_weapi_request(
            APIConstants.PLAYLIST_MANIPULATE_API, payload, cookies_copy
        )
        result = json.loads(response_text)
        if result.get('code') != 200:
            raise APIException(
                f"歌单操作失败 (op={op}): {result.get('message', '未知错误')}"
            )
        return result

    def get_liked_playlist_id(self, uid: int, cookies: Dict[str, str]) -> int:
        """获取「我喜欢的音乐」歌单ID（specialType=5）"""
        data = self.get_user_playlist(uid, cookies)
        for pl in data.get('playlist', []):
            if pl.get('specialType') == 5:
                return pl['id']
        raise APIException("未找到「我喜欢的音乐」歌单，请确认已登录")


class QRLoginManager:
    
    def __init__(self):
        self.http_client = HTTPClient()
        self.crypto_utils = CryptoUtils()
    
    def generate_qr_key(self) -> Optional[str]:
        """生成二维码的key
        
        Returns:
            成功返回unikey，失败返回None
            
        Raises:
            APIException: API调用失败时抛出
        """
        try:
            config = APIConstants.DEFAULT_CONFIG.copy()
            config["requestId"] = str(randrange(20000000, 30000000))
            
            payload = {
                'type': 1,
                'header': json.dumps(config)
            }
            
            params = self.crypto_utils.encrypt_params(APIConstants.QR_UNIKEY_API, payload)
            response = self.http_client.post_request_full(APIConstants.QR_UNIKEY_API, params, {})
            
            result = json.loads(response.text)
            if result.get('code') == 200:
                return result.get('unikey')
            else:
                raise APIException(f"生成二维码key失败: {result.get('message', '未知错误')}")
        except (json.JSONDecodeError, KeyError) as e:
            raise APIException(f"解析二维码key响应失败: {e}")
    
    def create_qr_login(self) -> Optional[str]:
        """创建登录二维码并在控制台显示
        
        Returns:
            成功返回unikey，失败返回None
        """
        try:
            import qrcode
            
            unikey = self.generate_qr_key()
            if not unikey:
                print("生成二维码key失败")
                return None
            
            # 创建二维码
            qr = qrcode.QRCode()
            qr.add_data(f'https://music.163.com/login?codekey={unikey}')
            qr.make(fit=True)
            
            # 在控制台显示二维码
            qr.print_ascii(tty=True)
            print("\n请使用网易云音乐APP扫描上方二维码登录")
            return unikey
        except ImportError:
            print("请安装qrcode库: pip install qrcode")
            return None
        except Exception as e:
            print(f"创建二维码失败: {e}")
            return None
    
    def check_qr_login(self, unikey: str) -> Tuple[int, Dict[str, str]]:
        """检查二维码登录状态
        
        Args:
            unikey: 二维码key
            
        Returns:
            (登录状态码, cookie字典)
            
        Raises:
            APIException: API调用失败时抛出
        """
        try:
            config = APIConstants.DEFAULT_CONFIG.copy()
            config["requestId"] = str(randrange(20000000, 30000000))
            
            payload = {
                'key': unikey,
                'type': 1,
                'header': json.dumps(config)
            }
            
            params = self.crypto_utils.encrypt_params(APIConstants.QR_LOGIN_API, payload)
            response = self.http_client.post_request_full(APIConstants.QR_LOGIN_API, params, {})
            
            result = json.loads(response.text)
            cookie_dict = {}
            
            if result.get('code') == 803:
                # 登录成功，提取cookie
                all_cookies = response.headers.get('Set-Cookie', '').split(', ')
                for cookie_str in all_cookies:
                    if 'MUSIC_U=' in cookie_str:
                        cookie_dict['MUSIC_U'] = cookie_str.split('MUSIC_U=')[1].split(';')[0]
            
            return result.get('code', -1), cookie_dict
        except (json.JSONDecodeError, KeyError) as e:
            raise APIException(f"解析登录状态响应失败: {e}")
    
    def qr_login(self) -> Optional[str]:
        """完整的二维码登录流程
        
        Returns:
            成功返回cookie字符串，失败返回None
        """
        try:
            unikey = self.create_qr_login()
            if not unikey:
                return None
            
            while True:
                code, cookies = self.check_qr_login(unikey)
                
                if code == 803:
                    print("\n登录成功！")
                    return f"MUSIC_U={cookies['MUSIC_U']};os=pc;appver=8.9.70;"
                elif code == 801:
                    print("\r等待扫码...", end='')
                elif code == 802:
                    print("\r扫码成功，请在手机上确认登录...", end='')
                else:
                    print(f"\n登录失败，错误码：{code}")
                    return None
                
                time.sleep(2)
        except KeyboardInterrupt:
            print("\n用户取消登录")
            return None
        except Exception as e:
            print(f"\n登录过程中发生错误: {e}")
            return None


# 向后兼容的函数接口
def url_v1(song_id: int, level: str, cookies: Dict[str, str]) -> Dict[str, Any]:
    """获取歌曲URL（向后兼容）"""
    api = NeteaseAPI()
    return api.get_song_url(song_id, level, cookies)


def name_v1(song_id: int) -> Dict[str, Any]:
    """获取歌曲详情（向后兼容）"""
    api = NeteaseAPI()
    return api.get_song_detail(song_id)


def lyric_v1(song_id: int, cookies: Dict[str, str]) -> Dict[str, Any]:
    """获取歌词（向后兼容）"""
    api = NeteaseAPI()
    return api.get_lyric(song_id, cookies)


def search_music(keywords: str, cookies: Dict[str, str], limit: int = 10) -> List[Dict[str, Any]]:
    """搜索音乐（向后兼容）"""
    api = NeteaseAPI()
    return api.search_music(keywords, cookies, limit)


def playlist_detail(playlist_id: int, cookies: Dict[str, str]) -> Dict[str, Any]:
    """获取歌单详情（向后兼容）"""
    api = NeteaseAPI()
    return api.get_playlist_detail(playlist_id, cookies)


def album_detail(album_id: int, cookies: Dict[str, str]) -> Dict[str, Any]:
    """获取专辑详情（向后兼容）"""
    api = NeteaseAPI()
    return api.get_album_detail(album_id, cookies)


def get_pic_url(pic_id: Optional[int], size: int = 300) -> str:
    """获取图片URL（向后兼容）"""
    api = NeteaseAPI()
    return api.get_pic_url(pic_id, size)


def qr_login() -> Optional[str]:
    """二维码登录（向后兼容）"""
    manager = QRLoginManager()
    return manager.qr_login()


def set_like(track_id: int, like: bool, cookies: Dict[str, str]) -> Dict[str, Any]:
    """红心/取消红心歌曲（向后兼容）"""
    api = NeteaseAPI()
    return api.set_like(track_id, like, cookies)


def get_likelist(uid: int, cookies: Dict[str, str]) -> Dict[str, Any]:
    """获取喜欢列表（向后兼容）"""
    api = NeteaseAPI()
    return api.get_likelist(uid, cookies)


def user_account(cookies: Dict[str, str]) -> Dict[str, Any]:
    """获取当前用户账号信息（向后兼容）"""
    api = NeteaseAPI()
    return api.get_user_account(cookies)


def user_playlist(uid: int, cookies: Dict[str, str], limit: int = 30, offset: int = 0) -> Dict[str, Any]:
    """获取用户歌单（向后兼容）"""
    api = NeteaseAPI()
    return api.get_user_playlist(uid, cookies, limit, offset)


def manipulate_playlist_tracks(pid: int, track_ids: List[int], op: str, cookies: Dict[str, str]) -> Dict[str, Any]:
    """歌单添加/删除歌曲（向后兼容）"""
    api = NeteaseAPI()
    return api.manipulate_playlist_tracks(pid, track_ids, op, cookies)


def get_liked_playlist_id(uid: int, cookies: Dict[str, str]) -> int:
    """获取「我喜欢的音乐」歌单ID（向后兼容）"""
    api = NeteaseAPI()
    return api.get_liked_playlist_id(uid, cookies)


if __name__ == "__main__":
    # 测试代码
    print("网易云音乐API模块")
    print("支持的功能:")
    print("- 歌曲URL获取")
    print("- 歌曲详情获取")
    print("- 歌词获取")
    print("- 音乐搜索")
    print("- 歌单详情")
    print("- 专辑详情")
    print("- 二维码登录")
    print("- 喜欢/取消喜欢（红心）")
    print("- 获取喜欢列表")
    print("- 获取用户账号信息")
    print("- 获取用户歌单列表")
