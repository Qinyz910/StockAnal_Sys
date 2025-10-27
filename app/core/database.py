import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from datetime import datetime
from contextlib import contextmanager

# 读取配置
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/stock_analyzer.db')
USE_DATABASE = os.getenv('USE_DATABASE', 'False').lower() == 'true'

# 优化的引擎配置，添加连接池
engine_config = {
    'poolclass': QueuePool,
    'pool_size': 10,
    'max_overflow': 20,
    'pool_timeout': 30,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'echo': False,
}

# SQLite 特殊配置
if DATABASE_URL.startswith('sqlite'):
    engine_config['connect_args'] = {'check_same_thread': False}
    # SQLite doesn't support connection pooling the same way
    engine_config.pop('pool_size', None)
    engine_config.pop('max_overflow', None)

# 创建引擎
engine = create_engine(DATABASE_URL, **engine_config)
Base = declarative_base()


# 定义模型
class StockInfo(Base):
    __tablename__ = 'stock_info'
    __table_args__ = (
        Index('idx_stock_info_code_market', 'stock_code', 'market_type'),
        Index('idx_stock_info_updated_at', 'updated_at'),
    )

    id = Column(Integer, primary_key=True)
    stock_code = Column(String(10), nullable=False, index=True)
    stock_name = Column(String(50))
    market_type = Column(String(5))
    industry = Column(String(50))
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'market_type': self.market_type,
            'industry': self.industry,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }


class AnalysisResult(Base):
    __tablename__ = 'analysis_results'
    __table_args__ = (
        Index('idx_analysis_code_date', 'stock_code', 'analysis_date'),
        Index('idx_analysis_score', 'score'),
        Index('idx_analysis_date', 'analysis_date'),
    )

    id = Column(Integer, primary_key=True)
    stock_code = Column(String(10), nullable=False, index=True)
    market_type = Column(String(5))
    analysis_date = Column(DateTime, default=datetime.now)
    score = Column(Float)
    recommendation = Column(String(100))
    technical_data = Column(JSON)
    fundamental_data = Column(JSON)
    capital_flow_data = Column(JSON)
    ai_analysis = Column(Text)

    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'market_type': self.market_type,
            'analysis_date': self.analysis_date.strftime('%Y-%m-%d %H:%M:%S') if self.analysis_date else None,
            'score': self.score,
            'recommendation': self.recommendation,
            'technical_data': self.technical_data,
            'fundamental_data': self.fundamental_data,
            'capital_flow_data': self.capital_flow_data,
            'ai_analysis': self.ai_analysis
        }


class Portfolio(Base):
    __tablename__ = 'portfolios'
    __table_args__ = (
        Index('idx_portfolio_user_updated', 'user_id', 'updated_at'),
        Index('idx_portfolio_name', 'name'),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)
    name = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    stocks = Column(JSON)  # 存储股票列表的JSON

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
            'stocks': self.stocks
        }


# 创建线程安全的会话工厂
Session = scoped_session(sessionmaker(bind=engine))


# 初始化数据库
def init_db():
    Base.metadata.create_all(engine)


# 获取数据库会话（线程安全）
def get_session():
    return Session()


# 上下文管理器用于数据库会话
@contextmanager
def db_session_scope():
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# 批量查询辅助函数
def query_with_pagination(query, page=1, per_page=50):
    total = query.count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    return {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    }


def remove_session():
    Session.remove()


# 如果启用数据库，则初始化
if USE_DATABASE:
    init_db()