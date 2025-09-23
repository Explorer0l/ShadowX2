"""
Database connection pool for high-performance SQLite operations
"""

import sqlite3
import threading
import queue
import contextlib
from config import DATABASE_NAME, DB_CONNECTION_POOL_SIZE

class SQLitePool:
    def __init__(self, database_path: str, pool_size: int = 10):
        self.database_path = database_path
        self.pool_size = pool_size
        self._pool = queue.Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._initialized = False
        
    def _create_connection(self):
        """Create a new SQLite connection with optimized settings"""
        conn = sqlite3.connect(
            self.database_path, 
            timeout=30,
            check_same_thread=False,
            isolation_level=None  # Autocommit mode for better concurrency
        )
        # Performance optimizations
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA temp_store=MEMORY')
        conn.execute('PRAGMA cache_size=-65536')  # 64MB cache
        conn.execute('PRAGMA mmap_size=268435456')  # 256MB memory map
        return conn
    
    def _initialize_pool(self):
        """Initialize the connection pool"""
        if self._initialized:
            return
            
        with self._lock:
            if self._initialized:
                return
                
            for _ in range(self.pool_size):
                conn = self._create_connection()
                self._pool.put(conn)
            self._initialized = True
    
    @contextlib.contextmanager
    def get_connection(self):
        """Get a connection from the pool (context manager)"""
        if not self._initialized:
            self._initialize_pool()
            
        try:
            # Try to get connection with timeout
            conn = self._pool.get(timeout=5)
            yield conn
        except queue.Empty:
            # Pool exhausted, create temporary connection
            conn = self._create_connection()
            yield conn
        finally:
            # Return connection to pool if there's space
            try:
                self._pool.put_nowait(conn)
            except queue.Full:
                # Pool is full, close the connection
                conn.close()
    
    def close_all(self):
        """Close all connections in the pool"""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except queue.Empty:
                break

# Global pool instance
_db_pool = None

def get_db_pool():
    """Get the global database pool instance"""
    global _db_pool
    if _db_pool is None:
        _db_pool = SQLitePool(DATABASE_NAME, DB_CONNECTION_POOL_SIZE)
    return _db_pool

def get_db_connection():
    """Get a database connection from the pool"""
    return get_db_pool().get_connection()
