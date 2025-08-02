#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置密钥管理工具

功能：
- 生成和管理配置加密密钥
- 密钥轮换和备份
- 安全密钥存储
- 配置文件加密/解密
"""

import os
import sys
import argparse
import json
import time
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.utils.logger import get_logger

logger = get_logger(__name__)

class ConfigKeyManager:
    """配置密钥管理器"""
    
    def __init__(self, key_dir: Optional[str] = None):
        self.key_dir = Path(key_dir) if key_dir else project_root / 'config' / 'keys'
        self.key_dir.mkdir(parents=True, exist_ok=True)
        self.current_key_file = self.key_dir / 'current.key'
        self.backup_dir = self.key_dir / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
        
    def generate_key(self) -> bytes:
        """生成新的加密密钥"""
        return Fernet.generate_key()
    
    def save_key(self, key: bytes, backup_current: bool = True) -> str:
        """保存密钥到文件"""
        # 备份当前密钥
        if backup_current and self.current_key_file.exists():
            timestamp = int(time.time())
            backup_path = self.backup_dir / f'key_backup_{timestamp}.key'
            shutil.copy2(self.current_key_file, backup_path)
            logger.info(f"当前密钥已备份到: {backup_path}")
        
        # 保存新密钥
        with open(self.current_key_file, 'wb') as f:
            f.write(key)
        
        # 设置安全权限（仅所有者可读写）
        os.chmod(self.current_key_file, 0o600)
        
        logger.info(f"新密钥已保存到: {self.current_key_file}")
        return str(self.current_key_file)
    
    def load_key(self) -> Optional[bytes]:
        """加载当前密钥"""
        if not self.current_key_file.exists():
            logger.warning("密钥文件不存在")
            return None
        
        try:
            with open(self.current_key_file, 'rb') as f:
                key = f.read()
            
            # 验证密钥格式
            Fernet(key)  # 这会验证密钥格式
            return key
            
        except Exception as e:
            logger.error(f"加载密钥失败: {e}")
            return None
    
    def rotate_key(self) -> str:
        """轮换密钥"""
        logger.info("开始密钥轮换...")
        
        # 生成新密钥
        new_key = self.generate_key()
        
        # 保存新密钥（自动备份旧密钥）
        key_path = self.save_key(new_key, backup_current=True)
        
        logger.info("密钥轮换完成")
        return key_path
    
    def list_backups(self) -> list:
        """列出所有备份密钥"""
        backups = []
        for backup_file in self.backup_dir.glob('key_backup_*.key'):
            stat = backup_file.stat()
            backups.append({
                'file': str(backup_file),
                'timestamp': backup_file.stem.split('_')[-1],
                'size': stat.st_size,
                'created': stat.st_ctime
            })
        
        return sorted(backups, key=lambda x: x['created'], reverse=True)
    
    def restore_backup(self, backup_timestamp: str) -> bool:
        """从备份恢复密钥"""
        backup_file = self.backup_dir / f'key_backup_{backup_timestamp}.key'
        
        if not backup_file.exists():
            logger.error(f"备份文件不存在: {backup_file}")
            return False
        
        try:
            # 验证备份密钥
            with open(backup_file, 'rb') as f:
                backup_key = f.read()
            Fernet(backup_key)  # 验证密钥格式
            
            # 备份当前密钥
            if self.current_key_file.exists():
                current_backup = self.backup_dir / f'key_backup_before_restore_{int(time.time())}.key'
                shutil.copy2(self.current_key_file, current_backup)
                logger.info(f"当前密钥已备份到: {current_backup}")
            
            # 恢复备份密钥
            shutil.copy2(backup_file, self.current_key_file)
            os.chmod(self.current_key_file, 0o600)
            
            logger.info(f"密钥已从备份恢复: {backup_timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False
    
    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """清理旧备份，保留指定数量"""
        backups = self.list_backups()
        
        if len(backups) <= keep_count:
            logger.info(f"备份数量 ({len(backups)}) 未超过保留数量 ({keep_count})")
            return 0
        
        # 删除多余的备份
        deleted_count = 0
        for backup in backups[keep_count:]:
            try:
                os.remove(backup['file'])
                deleted_count += 1
                logger.info(f"删除旧备份: {backup['file']}")
            except Exception as e:
                logger.warning(f"删除备份失败 {backup['file']}: {e}")
        
        logger.info(f"清理了 {deleted_count} 个旧备份")
        return deleted_count
    
    def migrate_legacy_key(self) -> bool:
        """迁移旧的.config_key文件"""
        legacy_key_file = project_root / '.config_key'
        
        if not legacy_key_file.exists():
            logger.info("未找到旧的密钥文件")
            return False
        
        try:
            # 读取旧密钥
            with open(legacy_key_file, 'rb') as f:
                legacy_key = f.read()
            
            # 验证密钥格式
            Fernet(legacy_key)
            
            # 保存到新位置
            self.save_key(legacy_key, backup_current=False)
            
            # 备份旧文件
            legacy_backup = self.backup_dir / f'legacy_config_key_{int(time.time())}.key'
            shutil.copy2(legacy_key_file, legacy_backup)
            
            # 删除旧文件
            os.remove(legacy_key_file)
            
            logger.info(f"旧密钥文件已迁移，备份保存在: {legacy_backup}")
            return True
            
        except Exception as e:
            logger.error(f"迁移旧密钥文件失败: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取密钥管理状态"""
        current_key_exists = self.current_key_file.exists()
        legacy_key_exists = (project_root / '.config_key').exists()
        backups = self.list_backups()
        
        status = {
            'key_dir': str(self.key_dir),
            'current_key_exists': current_key_exists,
            'legacy_key_exists': legacy_key_exists,
            'backup_count': len(backups),
            'backups': backups[:5]  # 只显示最近5个备份
        }
        
        if current_key_exists:
            stat = self.current_key_file.stat()
            status['current_key'] = {
                'file': str(self.current_key_file),
                'size': stat.st_size,
                'created': stat.st_ctime,
                'permissions': oct(stat.st_mode)[-3:]
            }
        
        return status

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='配置密钥管理工具')
    parser.add_argument('--key-dir', help='密钥目录路径')
    parser.add_argument('--generate', action='store_true', help='生成新密钥')
    parser.add_argument('--rotate', action='store_true', help='轮换密钥')
    parser.add_argument('--migrate', action='store_true', help='迁移旧密钥文件')
    parser.add_argument('--status', action='store_true', help='显示状态')
    parser.add_argument('--list-backups', action='store_true', help='列出备份')
    parser.add_argument('--restore', help='从备份恢复密钥（指定时间戳）')
    parser.add_argument('--cleanup', type=int, metavar='COUNT', help='清理旧备份，保留指定数量')
    parser.add_argument('--json', action='store_true', help='JSON格式输出')
    
    args = parser.parse_args()
    
    manager = ConfigKeyManager(args.key_dir)
    result = {}
    
    try:
        if args.generate:
            key = manager.generate_key()
            key_path = manager.save_key(key)
            result = {'key_generated': True, 'key_path': key_path}
            
        elif args.rotate:
            key_path = manager.rotate_key()
            result = {'key_rotated': True, 'key_path': key_path}
            
        elif args.migrate:
            success = manager.migrate_legacy_key()
            result = {'migration_success': success}
            
        elif args.list_backups:
            backups = manager.list_backups()
            result = {'backups': backups}
            
        elif args.restore:
            success = manager.restore_backup(args.restore)
            result = {'restore_success': success, 'timestamp': args.restore}
            
        elif args.cleanup is not None:
            deleted_count = manager.cleanup_old_backups(args.cleanup)
            result = {'deleted_count': deleted_count, 'keep_count': args.cleanup}
            
        else:
            result = manager.get_status()
        
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            logger.info("操作完成")
            
    except Exception as e:
        logger.error(f"操作失败: {e}")
        if args.json:
            print(json.dumps({'error': str(e)}, ensure_ascii=False))
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)