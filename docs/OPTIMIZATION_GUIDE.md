# StockAnal_Sys 开发优化指南

本指南为开发者提供了编写高性能代码的最佳实践。

## Pandas 优化

### 1. 使用向量化操作

```python
# ❌ 不推荐 - 循环操作
for i in range(len(df)):
    df.loc[i, 'result'] = df.loc[i, 'close'] * 1.1

# ✅ 推荐 - 向量化操作
df['result'] = df['close'] * 1.1
```

### 2. 避免 iterrows()

```python
# ❌ 不推荐
total = 0
for idx, row in df.iterrows():
    total += row['value']

# ✅ 推荐
total = df['value'].sum()
```

### 3. 使用 apply() 时注意性能

```python
# ❌ 慢 - 使用 apply 处理简单运算
df['result'] = df.apply(lambda row: row['a'] + row['b'], axis=1)

# ✅ 快 - 直接向量化
df['result'] = df['a'] + df['b']

# ✅ 对于复杂逻辑，使用 np.vectorize
@np.vectorize
def complex_calc(a, b):
    if a > b:
        return a * 2
    return b * 2

df['result'] = complex_calc(df['a'].values, df['b'].values)
```

### 4. 使用 inplace 参数

```python
# ❌ 创建副本
df = df.drop(columns=['col1'])

# ✅ 原地修改
df.drop(columns=['col1'], inplace=True)
```

### 5. 批量操作而非单个

```python
# ❌ 逐行添加
for item in data:
    df = df.append(item, ignore_index=True)

# ✅ 批量添加
df = pd.concat([df, pd.DataFrame(data)], ignore_index=True)
```

### 6. 选择合适的数据类型

```python
# 优化内存使用
df['int_col'] = df['int_col'].astype('int32')  # 而非 int64
df['cat_col'] = df['cat_col'].astype('category')  # 分类数据
df['float_col'] = df['float_col'].astype('float32')  # 而非 float64
```

## NumPy 优化

### 1. 使用内置函数

```python
# ❌ 慢
result = np.zeros(len(arr))
for i in range(len(arr)):
    result[i] = arr[i] ** 2

# ✅ 快
result = np.square(arr)
```

### 2. 广播机制

```python
# ❌ 显式循环
matrix = np.zeros((1000, 100))
for i in range(1000):
    matrix[i, :] = arr * i

# ✅ 广播
matrix = arr * np.arange(1000)[:, np.newaxis]
```

### 3. 使用布尔索引

```python
# ❌ 循环筛选
result = []
for x in arr:
    if x > 0:
        result.append(x * 2)

# ✅ 布尔索引
result = arr[arr > 0] * 2
```

## 缓存使用

### 1. 装饰器缓存

```python
from app.core.cache_manager import cached

@cached(cache_type='analysis_result', ttl=900)
def analyze_stock(stock_code):
    # 耗时分析
    return result
```

### 2. 手动缓存控制

```python
from app.core.cache_manager import cache_manager

# 检查缓存
cached = cache_manager.get(f'analysis:{stock_code}', 'analysis_result')
if cached:
    return cached

# 执行计算
result = expensive_calculation()

# 保存到缓存
cache_manager.set(f'analysis:{stock_code}', result, 'analysis_result', ttl=900)
```

## 性能监控

### 1. 监控关键函数

```python
from app.core.performance_monitor import monitor_performance

@monitor_performance('my_module.expensive_function')
def expensive_function():
    # 耗时操作
    return result
```

### 2. 检查性能指标

```python
from app.core.performance_monitor import performance_monitor

# 获取统计信息
stats = performance_monitor.get_metrics()
slow_queries = performance_monitor.get_slow_queries()
```

## 数据库优化

### 1. 使用批量操作

```python
# ❌ 逐条插入
for item in items:
    session.add(StockInfo(**item))
    session.commit()

# ✅ 批量插入
session.bulk_insert_mappings(StockInfo, items)
session.commit()
```

### 2. 使用上下文管理器

```python
from app.core.database import db_session_scope

with db_session_scope() as session:
    results = session.query(StockInfo).filter_by(market_type='A').all()
    # 自动处理 commit/rollback/close
```

### 3. 延迟加载优化

```python
# 使用 joinedload 减少查询次数
from sqlalchemy.orm import joinedload

query = session.query(Portfolio).options(
    joinedload(Portfolio.stocks)
).filter_by(user_id='123')
```

## 异步处理

### 1. 使用线程池

```python
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=10)

# 提交任务
future = executor.submit(heavy_task, arg1, arg2)

# 获取结果
result = future.result(timeout=30)
```

### 2. 批量并发

```python
from concurrent.futures import as_completed

tasks = [executor.submit(process_stock, code) for code in stock_codes]

results = []
for future in as_completed(tasks):
    try:
        result = future.result()
        results.append(result)
    except Exception as e:
        logger.error(f"任务失败: {e}")
```

## 代码优化清单

- [ ] 使用向量化操作替代循环
- [ ] 避免不必要的数据复制
- [ ] 为频繁调用的函数添加缓存
- [ ] 使用合适的数据类型减少内存
- [ ] 添加性能监控装饰器
- [ ] 数据库查询使用批量操作
- [ ] 耗时操作使用异步处理
- [ ] 避免在循环中进行 I/O 操作
- [ ] 使用生成器处理大数据集
- [ ] 定期检查性能指标和慢查询

## 性能测试

### 1. 简单计时

```python
import time

start = time.time()
# 待测试代码
duration = time.time() - start
print(f"耗时: {duration:.3f}秒")
```

### 2. 使用 cProfile

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# 待测试代码

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # 显示前20个最耗时的函数
```

### 3. 内存分析

```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    # 代码
    pass
```

## 常见性能陷阱

### 1. 字符串拼接

```python
# ❌ 慢 - 在循环中拼接字符串
result = ""
for item in items:
    result += str(item)

# ✅ 快 - 使用 join
result = "".join(str(item) for item in items)
```

### 2. 列表推导式 vs map/filter

```python
# 对于简单操作，列表推导式通常更快
# ✅ 推荐
result = [x * 2 for x in items if x > 0]

# 对于复杂函数，map 可能更快
# ✅ 也可以
result = list(map(complex_function, items))
```

### 3. 全局变量查找

```python
# ❌ 慢 - 全局变量查找
import math
for i in range(1000000):
    x = math.sqrt(i)

# ✅ 快 - 局部变量
sqrt = math.sqrt
for i in range(1000000):
    x = sqrt(i)
```

## 更多资源

- [Pandas Performance Guide](https://pandas.pydata.org/docs/user_guide/enhancingperf.html)
- [NumPy Performance Tips](https://numpy.org/doc/stable/user/basics.performance.html)
- [Python Performance Tips](https://wiki.python.org/moin/PythonSpeed/PerformanceTips)
