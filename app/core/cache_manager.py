"""
多级缓存管理器
提供内存缓存 + Redis 缓存的多级缓存策略
"""
import os
import time
import json
import logging
import hashlib
from typing import Any, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheManager:
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.memory_cache = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'memory_hits': 0,
            'redis_hits': 0
        }
        
        # 缓存TTL配置（秒）
        self.ttl_config = {
            'stock_data': 300,  # 5分钟
            'technical_indicators': 600,  # 10分钟
            'analysis_result': 900,  # 15分钟
            'market_scan': 1800,  # 30分钟
            'news': 600,  # 10分钟
            'fundamental': 3600,  # 1小时
            'capital_flow': 900,  # 15分钟
            'quick': 60,  # 1分钟 - 快速缓存
            'long': 7200,  # 2小时 - 长期缓存
        }
    
    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        key_parts = [prefix]
        key_parts.extend([str(arg) for arg in args])
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
        key_str = ":".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()[:16] + "_" + key_str[:50]
    
    def get(self, key: str, cache_type: str = 'stock_data') -> Optional[Any]:
        # 先检查内存缓存
        if key in self.memory_cache:
            cached_item = self.memory_cache[key]
            if cached_item['expiry'] > time.time():
                self.cache_stats['hits'] += 1
                self.cache_stats['memory_hits'] += 1
                logger.debug(f"内存缓存命中: {key}")
                return cached_item['value']
            else:
                del self.memory_cache[key]
        
        # 检查Redis缓存
        if self.redis_client:
            try:
                cached = self.redis_client.get(key)
                if cached:
                    value = json.loads(cached)
                    # 回填到内存缓存
                    ttl = self.ttl_config.get(cache_type, 300)
                    self.memory_cache[key] = {
                        'value': value,
                        'expiry': time.time() + min(ttl, 300)  # 内存缓存最多5分钟
                    }
                    self.cache_stats['hits'] += 1
                    self.cache_stats['redis_hits'] += 1
                    logger.debug(f"Redis缓存命中: {key}")
                    return value
            except Exception as e:
                logger.error(f"Redis缓存读取失败: {e}")
        
        self.cache_stats['misses'] += 1
        return None
    
    def set(self, key: str, value: Any, cache_type: str = 'stock_data', ttl: Optional[int] = None):
        if ttl is None:
            ttl = self.ttl_config.get(cache_type, 300)
        
        # 设置内存缓存
        self.memory_cache[key] = {
            'value': value,
            'expiry': time.time() + min(ttl, 300)
        }
        
        # 设置Redis缓存
        if self.redis_client:
            try:
                payload = json.dumps(value, default=str, ensure_ascii=False)
            except (TypeError, ValueError):
                logger.debug(f"数据无法序列化到Redis缓存, 跳过: {type(value)}")
            else:
                try:
                    self.redis_client.setex(
                        key,
                        ttl,
                        payload
                    )
                    logger.debug(f"设置缓存: {key}, TTL: {ttl}s")
                except Exception as e:
                    logger.error(f"Redis缓存写入失败: {e}")
    
    def delete(self, key: str):
        if key in self.memory_cache:
            del self.memory_cache[key]
        
        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception as e:
                logger.error(f"Redis缓存删除失败: {e}")
    
    def clear(self, pattern: Optional[str] = None):
        if pattern:
            keys_to_delete = [k for k in self.memory_cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self.memory_cache[key]
            
            if self.redis_client:
                try:
                    for key in self.redis_client.scan_iter(match=f"*{pattern}*"):
                        self.redis_client.delete(key)
                except Exception as e:
                    logger.error(f"Redis批量删除失败: {e}")
        else:
            self.memory_cache.clear()
            if self.redis_client:
                try:
                    self.redis_client.flushdb()
                except Exception as e:
                    logger.error(f"Redis清空失败: {e}")
        
        logger.info(f"清空缓存, pattern: {pattern}")
    
    def get_stats(self):
        total = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total * 100) if total > 0 else 0
        return {
            **self.cache_stats,
            'hit_rate': f"{hit_rate:.2f}%",
            'memory_cache_size': len(self.memory_cache)
        }
    
    def cleanup_expired(self):
        current_time = time.time()
        expired_keys = [
            k for k, v in self.memory_cache.items()
            if v['expiry'] <= current_time
        ]
        for key in expired_keys:
            del self.memory_cache[key]
        
        if expired_keys:
            logger.info(f"清理过期缓存: {len(expired_keys)}个")
        
        return len(expired_keys)


def cached(cache_type: str = 'stock_data', ttl: Optional[int] = None, 
           key_prefix: Optional[str] = None):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, 'cache_manager'):
                return func(self, *args, **kwargs)
            
            prefix = key_prefix or f"{func.__module__}.{func.__name__}"
            cache_key = self.cache_manager._generate_cache_key(prefix, *args, **kwargs)
            
            # 尝试从缓存获取
            cached_value = self.cache_manager.get(cache_key, cache_type)
            if cached_value is not None:
                return cached_value
            
            # 执行函数
            result = func(self, *args, **kwargs)
            
            # 存入缓存
            if result is not None:
                self.cache_manager.set(cache_key, result, cache_type, ttl)
            
            return result
        
        return wrapper
    return decorator


def create_cache_manager():
    redis_client = None
    if os.getenv('USE_REDIS_CACHE', 'False').lower() == 'true':
        try:
            import redis
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            redis_client = redis.from_url(redis_url, decode_responses=True)
            redis_client.ping()
            logger.info("Redis缓存已连接")
        except Exception as e:
            logger.warning(f"Redis连接失败，使用内存缓存: {e}")
            redis_client = None
    
    return CacheManager(redis_client)


# 全局缓存管理器实例
cache_manager = create_cache_manager()
