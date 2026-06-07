#!/usr/bin/env python3
"""
本地测试定时同步功能的Python脚本

使用方法：
    python test_sync_local.py
    
此脚本会：
1. 检查依赖是否安装
2. 验证配置文件
3. 启动服务并测试同步功能
"""

import sys
import os
from pathlib import Path


def check_dependencies():
    """检查依赖包是否安装"""
    print("=" * 60)
    print("步骤1: 检查依赖包")
    print("=" * 60)
    
    required_packages = [
        'flask',
        'requests',
        'cryptography',
        'mutagen',
        'qrcode',
        'apscheduler',
        'aiohttp',
        'aiofiles'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - 未安装")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  缺少以下依赖包: {', '.join(missing)}")
        print("\n请运行以下命令安装:")
        print("  pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple")
        return False
    
    print("\n✅ 所有依赖包已安装\n")
    return True


def check_files():
    """检查必要文件是否存在"""
    print("=" * 60)
    print("步骤2: 检查必要文件")
    print("=" * 60)
    
    required_files = [
        'main.py',
        'playlist_sync.py',
        'music_api.py',
        'music_downloader.py',
        'cookie_manager.py',
        '.env'
    ]
    
    missing = []
    for file in required_files:
        if Path(file).exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} - 不存在")
            missing.append(file)
    
    if missing:
        print(f"\n❌ 缺少必要文件: {', '.join(missing)}")
        return False
    
    print("\n✅ 所有必要文件存在\n")
    return True


def check_cookie():
    """检查Cookie配置"""
    print("=" * 60)
    print("步骤3: 检查Cookie配置")
    print("=" * 60)
    
    # 检查cookie.txt
    cookie_file = Path('cookie.txt')
    if cookie_file.exists() and cookie_file.stat().st_size > 0:
        content = cookie_file.read_text(encoding='utf-8').strip()
        if content and 'MUSIC_U' in content:
            print(f"  ✅ cookie.txt 存在且包含MUSIC_U")
            return True
        else:
            print(f"  ⚠️  cookie.txt 存在但可能无效")
            return False
    else:
        print(f"  ⚠️  cookie.txt 不存在或为空")
        print(f"     请使用以下方式之一获取Cookie:")
        print(f"       1. 运行: python qr_login.py (二维码登录)")
        print(f"       2. 手动从浏览器复制Cookie到 cookie.txt")
        return False


def check_env_config():
    """检查环境变量配置"""
    print("=" * 60)
    print("步骤4: 检查环境配置")
    print("=" * 60)
    
    # 读取.env文件
    env_file = Path('.env')
    if not env_file.exists():
        print("  ❌ .env 文件不存在")
        return False
    
    # 尝试多种编码读取
    content = None
    for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
        try:
            content = env_file.read_text(encoding=encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    if content is None:
        print("  ⚠️  无法读取.env文件（编码问题）")
        print("     建议：使用文本编辑器重新保存为UTF-8编码")
        return True  # 不阻断测试
    
    checks = {
        'ENABLE_SYNC': False,
        'PLAYLIST_IDS': False,
        'SYNC_QUALITY': False
    }
    
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('#') or not line:
            continue
        
        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            if key in checks:
                if value:
                    checks[key] = True
                    print(f"  ✅ {key} = {value}")
                else:
                    print(f"  ⚠️  {key} 未设置")
    
    if not checks['ENABLE_SYNC']:
        print("\n  ⚠️  建议在.env中设置 ENABLE_SYNC=true")
    
    if not checks['PLAYLIST_IDS']:
        print("  ⚠️  建议在.env中设置 PLAYLIST_IDS=你的歌单ID")
        print("     例如: PLAYLIST_IDS=1234567890,9876543210")
    
    print()
    return True


def print_test_instructions():
    """打印测试说明"""
    print("=" * 60)
    print("📋 测试说明")
    print("=" * 60)
    print()
    print("1️⃣  准备Cookie:")
    print("   - 方式1: python qr_login.py (推荐)")
    print("   - 方式2: 手动复制浏览器Cookie到 cookie.txt")
    print()
    print("2️⃣  配置歌单ID:")
    print("   - 编辑 .env 文件")
    print("   - 设置 PLAYLIST_IDS=你的歌单ID")
    print("   - 多个歌单用逗号分隔，如: 123,456,789")
    print()
    print("3️⃣  启动服务:")
    print("   - 运行: python main.py")
    print("   - 或在PowerShell中: .\\test_sync.bat")
    print()
    print("4️⃣  测试API:")
    print("   - 查看同步状态: http://localhost:5000/sync/status")
    print("   - 立即执行同步: http://localhost:5000/sync/now")
    print()
    print("5️⃣  查看日志:")
    print("   - playlist_sync.log - 同步日志")
    print("   - music_api.log - API日志")
    print()
    print("=" * 60)


def quick_test():
    """快速测试（不启动完整服务）"""
    print("=" * 60)
    print("🧪 快速功能测试")
    print("=" * 60)
    print()
    
    try:
        from playlist_sync import PlaylistSyncConfig, PlaylistSyncService
        
        print("✅ playlist_sync 模块导入成功")
        
        # 创建测试配置
        config = PlaylistSyncConfig(
            playlist_ids=['test123'],
            quality='lossless',
            sync_interval=3600,
            download_dir='test_downloads'
        )
        
        print("✅ PlaylistSyncConfig 创建成功")
        print(f"   - 歌单ID: {config.playlist_ids}")
        print(f"   - 音质: {config.quality}")
        print(f"   - 间隔: {config.sync_interval}秒")
        
        # 测试服务初始化
        service = PlaylistSyncService(config)
        print("✅ PlaylistSyncService 初始化成功")
        
        # 清理测试目录
        import shutil
        test_dir = Path('test_downloads')
        if test_dir.exists():
            shutil.rmtree(test_dir)
        
        print("\n✅ 快速测试通过！核心功能正常。")
        return True
        
    except Exception as e:
        print(f"\n❌ 快速测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "🎵" * 30)
    print("网易云音乐定时同步功能 - 本地测试工具")
    print("🎵" * 30 + "\n")
    
    # 执行检查
    checks_passed = True
    
    if not check_dependencies():
        checks_passed = False
    
    if not check_files():
        checks_passed = False
    
    check_cookie()  # Cookie不是必须的，只是警告
    check_env_config()
    
    if checks_passed:
        # 快速功能测试
        quick_test()
        
        print()
        print_test_instructions()
        
        # 询问是否启动服务
        response = input("\n是否现在启动服务进行测试? (y/n): ")
        if response.lower() == 'y':
            print("\n启动服务...")
            os.system('python main.py')
    else:
        print("\n❌ 请先解决上述问题后再进行测试")
        print_test_instructions()


if __name__ == '__main__':
    main()
