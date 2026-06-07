"""
快速功能测试 - 不启动完整服务，只测试核心功能
"""

import sys
from pathlib import Path


def test_imports():
    """测试模块导入"""
    print("=" * 60)
    print("Test 1: Module Imports")
    print("=" * 60)
    
    modules = [
        ('flask', 'Flask web framework'),
        ('requests', 'HTTP library'),
        ('cryptography', 'Encryption library'),
        ('mutagen', 'Audio tagging'),
        ('qrcode', 'QR code generation'),
        ('apscheduler', 'Task scheduler'),
        ('aiohttp', 'Async HTTP'),
        ('aiofiles', 'Async file I/O'),
    ]
    
    failed = []
    for module, desc in modules:
        try:
            __import__(module)
            print(f"  ✓ {module:20} - {desc}")
        except ImportError as e:
            print(f"  ✗ {module:20} - FAILED: {e}")
            failed.append(module)
    
    if failed:
        print(f"\n✗ Import test FAILED for: {', '.join(failed)}")
        return False
    
    print("\n✓ All imports successful!\n")
    return True


def test_custom_modules():
    """测试自定义模块"""
    print("=" * 60)
    print("Test 2: Custom Modules")
    print("=" * 60)
    
    custom_modules = [
        ('playlist_sync', 'Playlist sync service'),
        ('music_api', 'Netease API'),
        ('music_downloader', 'Music downloader'),
        ('cookie_manager', 'Cookie manager'),
    ]
    
    failed = []
    for module, desc in custom_modules:
        try:
            __import__(module)
            print(f"  ✓ {module:25} - {desc}")
        except ImportError as e:
            print(f"  ✗ {module:25} - FAILED: {e}")
            failed.append(module)
    
    if failed:
        print(f"\n✗ Custom module test FAILED for: {', '.join(failed)}")
        return False
    
    print("\n✓ All custom modules loaded!\n")
    return True


def test_sync_config():
    """测试同步配置"""
    print("=" * 60)
    print("Test 3: Sync Configuration")
    print("=" * 60)
    
    try:
        from playlist_sync import PlaylistSyncConfig
        
        config = PlaylistSyncConfig(
            playlist_ids=['test123'],
            quality='lossless',
            sync_interval=60
        )
        
        print(f"  ✓ Created config successfully")
        print(f"    - Playlist IDs: {config.playlist_ids}")
        print(f"    - Quality: {config.quality}")
        print(f"    - Interval: {config.sync_interval}s")
        print(f"    - Download dir: {config.download_dir}")
        print("\n✓ Configuration test passed!\n")
        return True
        
    except Exception as e:
        print(f"  ✗ Configuration test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sync_service_init():
    """测试服务初始化"""
    print("=" * 60)
    print("Test 4: Service Initialization")
    print("=" * 60)
    
    try:
        from playlist_sync import PlaylistSyncConfig, PlaylistSyncService
        import shutil
        
        # 创建测试配置
        config = PlaylistSyncConfig(
            playlist_ids=['test123'],
            quality='standard',
            sync_interval=60,
            download_dir='test_downloads'
        )
        
        # 初始化服务
        service = PlaylistSyncService(config)
        print(f"  ✓ Service initialized successfully")
        print(f"    - Logger configured")
        print(f"    - Scheduler created")
        print(f"    - Download directory: {service.downloads_path}")
        
        # 清理测试目录
        test_dir = Path('test_downloads')
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"    - Test directory cleaned")
        
        print("\n✓ Service initialization test passed!\n")
        return True
        
    except Exception as e:
        print(f"  ✗ Service initialization FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cookie_manager():
    """测试Cookie管理器"""
    print("=" * 60)
    print("Test 5: Cookie Manager")
    print("=" * 60)
    
    try:
        from cookie_manager import CookieManager
        
        manager = CookieManager()
        info = manager.get_cookie_info()
        
        print(f"  ✓ Cookie manager initialized")
        print(f"    - File exists: {info.get('file_exists', False)}")
        print(f"    - File size: {info.get('file_size', 0)} bytes")
        print(f"    - Is valid: {info.get('is_valid', False)}")
        
        if not info.get('is_valid', False):
            print(f"\n  ⚠ Warning: Cookie is not valid or empty")
            print(f"    Please run: python qr_login.py")
        else:
            print(f"    - Cookie count: {info.get('cookie_count', 0)}")
        
        print("\n✓ Cookie manager test completed!\n")
        return True
        
    except Exception as e:
        print(f"  ✗ Cookie manager test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_summary(results):
    """打印测试总结"""
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status:8} - {test_name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print("-" * 60)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your environment is ready.")
        print("\nNext steps:")
        print("  1. Run: python setup_config.bat (to configure)")
        print("  2. Run: python main.py (to start service)")
        print("  3. Visit: http://localhost:5000/sync/status")
    else:
        print("\n⚠ Some tests failed. Please fix the issues above.")
    
    print("=" * 60)


def main():
    """主测试函数"""
    print("\n" + "🎵" * 30)
    print("Netease Music Sync - Quick Function Test")
    print("🎵" * 30 + "\n")
    
    results = []
    
    # 执行测试
    results.append(("Module Imports", test_imports()))
    results.append(("Custom Modules", test_custom_modules()))
    results.append(("Sync Configuration", test_sync_config()))
    results.append(("Service Initialization", test_sync_service_init()))
    results.append(("Cookie Manager", test_cookie_manager()))
    
    # 打印总结
    print_summary(results)
    
    # 返回退出码
    all_passed = all(p for _, p in results)
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
