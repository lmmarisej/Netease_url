"""认证模块

提供用户认证、Token 签发/验证、线程上下文管理、用户注册。

使用 itsdangerous 进行 Token 签名（Flask 内置依赖，无需额外安装）：
- Token 有效期为 24 小时
- 使用 HMAC-SHA256 签名防篡改
- 线程本地存储用户上下文
"""

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
from functools import wraps

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import request, g

logger = logging.getLogger('music_api')

# ==================== 项目根目录 ====================

_PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent

# ==================== 配置常量 ====================

USERS_FILE = str(_PROJECT_ROOT / 'config' / 'users.json')
# 密钥，生产环境应使用环境变量覆盖
SECRET_KEY = 'netease-music-toolbox-secret-key-2024'
TOKEN_MAX_AGE = 86400  # Token 有效期：24 小时（秒）

# ==================== 线程本地存储 ====================

_thread_local = threading.local()


def get_current_user() -> Optional[str]:
    """获取当前请求的用户名（线程安全）

    优先从 Flask g 对象获取，其次从线程本地变量获取。
    """
    try:
        from flask import g
        user = g.get('_auth_user', None)
        if user:
            return user
    except RuntimeError:
        pass
    return getattr(_thread_local, 'username', None)


def set_current_user(username: str) -> None:
    """设置当前请求的用户名到线程上下文"""
    try:
        from flask import g
        g._auth_user = username
    except RuntimeError:
        _thread_local.username = username


# ==================== 用户管理 ====================

def load_users() -> Dict[str, str]:
    """从 config/users.json 加载用户列表

    Returns:
        {username: password} 字典
    """
    users_path = Path(USERS_FILE)
    if not users_path.exists():
        return {}

    try:
        with open(users_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return {}

    users = {}
    for u in data.get('users', []):
        username = u.get('username', '').strip()
        password = u.get('password', '')
        if username:
            users[username] = password
    return users


def verify_credentials(username: str, password: str) -> bool:
    """验证用户名和密码

    Args:
        username: 用户名
        password: 明文密码

    Returns:
        验证是否通过
    """
    users = load_users()
    stored_password = users.get(username)
    
    # 调试日志：打印输入的和已有的用户名密码
    logger.info(f"[登录验证] 输入用户名: '{username}', 输入密码: '{password}'")
    logger.info(f"[登录验证] 已有用户列表: {list(users.keys())}")
    if stored_password is None:
        logger.warning(f"[登录验证] 用户 '{username}' 不存在，已有用户: {list(users.keys())}")
        return False
    if stored_password != password:
        logger.warning(
            f"[登录验证] 密码不匹配 - 用户名: '{username}', "
            f"输入密码: '{password}', 已有密码: '{stored_password}'"
        )
        return False
    return True


# ==================== 用户注册 ====================

# 用户名正则：3-20 位，字母/数字/下划线/中文
_USERNAME_PATTERN = re.compile(r'^[\w\u4e00-\u9fff]{3,20}$')


def save_users(users_data: Dict[str, Any]) -> None:
    """保存用户数据到 config/users.json

    Args:
        users_data: 完整的用户数据字典，格式 {"users": [{"username": "...", "password": "..."}]}
    """
    users_path = Path(USERS_FILE)
    users_path.parent.mkdir(parents=True, exist_ok=True)
    with open(users_path, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, ensure_ascii=False, indent=2)


def register_user(username: str, password: str) -> Tuple[bool, str]:
    """注册新用户

    校验规则：
    - 用户名：3-20 位，字母/数字/下划线/中文
    - 密码：≥6 位
    - 查重：检查是否已存在

    成功后：
    - 写入 config/users.json 追加新用户
    - 创建 config/users/<username>/ 目录及默认配置文件

    Args:
        username: 用户名
        password: 明文密码

    Returns:
        (success, message) 元组
    """
    username = username.strip()
    password = password.strip()

    # 1. 校验用户名格式
    if not _USERNAME_PATTERN.match(username):
        return False, "用户名需为 3-20 位字母、数字、下划线或中文"

    # 2. 校验密码长度
    if len(password) < 6:
        return False, "密码长度至少 6 位"

    # 3. 查重
    users_path = Path(USERS_FILE)
    if users_path.exists():
        try:
            with open(users_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {"users": []}
    else:
        data = {"users": []}

    existing_users = {u.get('username', '') for u in data.get('users', [])}
    if username in existing_users:
        return False, f"用户名 '{username}' 已存在"

    # 4. 写入 users.json
    data.setdefault('users', []).append({"username": username, "password": password})
    save_users(data)

    # 5. 创建用户专属目录及默认配置文件
    user_dir = get_user_config_dir(username)
    user_dir.mkdir(parents=True, exist_ok=True)

    default_configs = {
        'settings.json': {'theme': 'auto', 'language': 'zh-CN'},
        'sync_config.json': {'enabled': False, 'playlist_ids': [], 'interval': 3600},
        'push_config.json': {'enabled': False, 'webhook_url': '', 'channels': []},
        'cookies.json': {},
    }

    for filename, content in default_configs.items():
        config_path = user_dir / filename
        if not config_path.exists():
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=2)

    logger.info(f"用户注册成功: {username}")
    return True, f"注册成功，欢迎 {username}"


# ==================== Token 管理 ====================

_serializer = URLSafeTimedSerializer(SECRET_KEY)


def generate_token(username: str) -> str:
    """为用户生成签名 Token

    Args:
        username: 用户名

    Returns:
        签名的 Token 字符串
    """
    return _serializer.dumps({'username': username})


def verify_token(token: str) -> Optional[str]:
    """验证 Token 并返回用户名

    Args:
        token: Token 字符串

    Returns:
        用户名，验证失败返回 None
    """
    try:
        data = _serializer.loads(token, max_age=TOKEN_MAX_AGE)
        return data.get('username')
    except (BadSignature, SignatureExpired):
        return None


# ==================== Flask 装饰器 ====================

def login_required(f):
    """Flask 路由装饰器：要求登录

    从 Authorization header 中提取 Bearer token 并验证。
    验证通过后将用户名存入 g._auth_user 和线程本地变量。

    用法:
        @app.route('/api/protected')
        @login_required
        def protected():
            username = get_current_user()
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token_from_request()
        if not token:
            from main import APIResponse
            return APIResponse.error("未提供认证Token", 401)

        username = verify_token(token)
        if not username:
            from main import APIResponse
            return APIResponse.error("Token无效或已过期，请重新登录", 401)

        set_current_user(username)
        return f(*args, **kwargs)
    return decorated


def _extract_token_from_request() -> Optional[str]:
    """从请求中提取 Bearer token"""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    # 也支持从 query 参数获取（用于文件下载等场景）
    token = request.args.get('token', '')
    if token:
        return token
    return None


# ==================== 用户配置路径 ====================

def get_user_config_dir(username: str) -> Path:
    """获取用户专属配置目录

    Args:
        username: 用户名

    Returns:
        用户配置目录路径，如 config/users/admin/
    """
    user_dir = _PROJECT_ROOT / 'config' / 'users' / username
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def get_user_downloads_dir(username: str) -> Path:
    """获取用户专属下载目录

    Args:
        username: 用户名

    Returns:
        用户下载目录路径，如 downloads/admin/
    """
    downloads_dir = _PROJECT_ROOT / 'downloads' / username
    downloads_dir.mkdir(parents=True, exist_ok=True)
    return downloads_dir


def get_user_config_path(username: str, config_name: str) -> Path:
    """获取用户专属配置文件路径

    Args:
        username: 用户名
        config_name: 配置文件名，如 settings.json, push_config.json

    Returns:
        配置文件完整路径
    """
    return get_user_config_dir(username) / config_name
