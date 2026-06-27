"""
认证相关路由：登录、注册、Token 验证

register_auth_routes(app, api_service) → 向 Flask app 注册认证路由
"""

from flask import request

from backend.auth import (
    verify_credentials, generate_token,
    get_current_user, set_current_user,
    register_user,
)
from backend.api_core import APIResponse


def register_auth_routes(app, api_service):
    """注册认证路由"""

    @app.route('/api/auth/login', methods=['POST'])
    def auth_login():
        try:
            data = request.get_json(silent=True) or {}
            username = data.get('username', '').strip()
            password = data.get('password', '')

            api_service.logger.info(f"[登录请求] 接收到用户名: '{username}', 密码: '{password}'")

            if not username or not password:
                api_service.logger.warning("[登录请求] 用户名或密码为空")
                return APIResponse.error("用户名和密码不能为空", 400)

            if not verify_credentials(username, password):
                api_service.logger.warning(f"[登录请求] 验证失败 - 用户名: '{username}', 密码: '{password}'")
                return APIResponse.error("用户名或密码错误", 401)

            token = generate_token(username)
            set_current_user(username)
            api_service.logger.info(f"用户登录成功: {username}")
            return APIResponse.success({'token': token, 'username': username}, "登录成功")
        except Exception as e:
            api_service.logger.error(f"登录异常: {e}")
            return APIResponse.error(f"登录失败: {str(e)}", 500)

    @app.route('/api/auth/register', methods=['POST'])
    def auth_register():
        try:
            data = request.get_json(silent=True) or {}
            username = data.get('username', '').strip()
            password = data.get('password', '')

            if not username or not password:
                return APIResponse.error("用户名和密码不能为空", 400)

            success, message = register_user(username, password)
            if not success:
                return APIResponse.error(message, 409)

            token = generate_token(username)
            set_current_user(username)
            api_service.logger.info(f"用户注册并自动登录: {username}")
            return APIResponse.success({'token': token, 'username': username}, message)
        except Exception as e:
            api_service.logger.error(f"注册异常: {e}")
            return APIResponse.error(f"注册失败: {str(e)}", 500)

    @app.route('/api/auth/verify', methods=['GET'])
    def auth_verify():
        username = get_current_user()
        if not username:
            return APIResponse.error("Token无效或已过期", 401)
        return APIResponse.success({'username': username, 'valid': True}, "Token有效")

