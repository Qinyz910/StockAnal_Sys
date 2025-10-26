"""
性能监控模块
用于追踪API响应时间、数据库查询性能等关键指标
"""
import time
import logging
from functools import wraps
from typing import Dict, List
from collections import defaultdict
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    def __init__(self):
        self.metrics = defaultdict(lambda: {
            'count': 0,
            'total_time': 0,
            'min_time': float('inf'),
            'max_time': 0,
            'errors': 0
        })
        self.lock = threading.Lock()
        self.slow_query_threshold = 1.0  # 慢查询阈值（秒）
        self.slow_queries = []
    
    def record_metric(self, name: str, duration: float, success: bool = True):
        with self.lock:
            metric = self.metrics[name]
            metric['count'] += 1
            metric['total_time'] += duration
            metric['min_time'] = min(metric['min_time'], duration)
            metric['max_time'] = max(metric['max_time'], duration)
            if not success:
                metric['errors'] += 1
            
            # 记录慢查询
            if duration > self.slow_query_threshold:
                self.slow_queries.append({
                    'name': name,
                    'duration': duration,
                    'timestamp': datetime.now().isoformat()
                })
                # 只保留最近100条慢查询
                if len(self.slow_queries) > 100:
                    self.slow_queries = self.slow_queries[-100:]
    
    def get_metrics(self) -> Dict:
        with self.lock:
            result = {}
            for name, data in self.metrics.items():
                avg_time = data['total_time'] / data['count'] if data['count'] > 0 else 0
                result[name] = {
                    'count': data['count'],
                    'avg_time': f"{avg_time:.3f}s",
                    'min_time': f"{data['min_time']:.3f}s" if data['min_time'] != float('inf') else 'N/A',
                    'max_time': f"{data['max_time']:.3f}s",
                    'total_time': f"{data['total_time']:.3f}s",
                    'errors': data['errors'],
                    'error_rate': f"{(data['errors'] / data['count'] * 100):.2f}%" if data['count'] > 0 else '0%'
                }
            return result
    
    def get_slow_queries(self, limit: int = 20) -> List[Dict]:
        with self.lock:
            return sorted(
                self.slow_queries[-limit:],
                key=lambda x: x['duration'],
                reverse=True
            )
    
    def reset_metrics(self):
        with self.lock:
            self.metrics.clear()
            self.slow_queries.clear()
            logger.info("性能监控指标已重置")


# 全局性能监控器
performance_monitor = PerformanceMonitor()


def monitor_performance(metric_name: str = None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                performance_monitor.record_metric(name, duration, success)
                
                if duration > performance_monitor.slow_query_threshold:
                    logger.warning(f"慢操作: {name}, 耗时: {duration:.3f}s")
        
        return wrapper
    return decorator
