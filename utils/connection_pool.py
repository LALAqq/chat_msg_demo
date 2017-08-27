#!/usr/bin/env python
import logging
import threading
import MySQLdb

class ConnectionPool:
    def __init__(self, *args, **kwargs):
        self._args = args
        self.__kwargs = kwargs
        self._cache_pool = []
        self.lock = threading.Lock()
        conn = self.connect()
        conn.close()

    def connect(self):
        """get the connection from cache, otherwise establish a new connection"""
        with self.lock:
            try:
                logging.debug('get connection from pool')
                _conn = self._cache_pool.pop(0)
            except IndexError:
                logging.debug('make connection')
                _conn = SingleConnection(*self._args, **self.__kwargs)
            else:
                _conn.reconnect()
            _conn = PooledConnection(self, _conn)
            return _conn

    def cache(self, conn):
        """cache the connection for reuse"""
        with self.lock:
            logging.debug('cache connection')
            self._cache_pool.append(conn)

    def close(self):
        """close the cache pool"""
        logging.debug('close connection')
        while self._cache_pool:
            _conn = self._cache_pool.pop(0)
            try:
                _conn.close()
            except Exception, e:
                logging.warning("exception: %s" % e)

class PooledConnection:
    def __init__(self, cache_pool, conn):
        self._cache_pool = cache_pool
        self._conn = conn;

    def close(self):
        """cache the connection to database"""
        if self._conn:
            self._cache_pool.cache(self._conn)
            self._conn = None

    def __getattr__(self, name):
        if self._conn:
            return getattr(self._conn, name)

class SingleConnection:
    def __init__(self, *args, **kwargs):
        self._args = args
        self.__kwargs = kwargs
        self._conn = MySQLdb.connect(*self._args, **self.__kwargs)
        self._conn.set_character_set("utf8")

    def reconnect(self):
        """reconnect if old connection is lost"""
        _reconnect = False
        try:
            self._conn.ping()
        except Exception, e:
            logging.warning("exception: %s" % e)
            logging.warning("start reconnection")
            _reconnect = True
        if _reconnect:
            try:
                _new_conn = MySQLdb.connect(*self._args, **self.__kwargs)
            except Exception, e:
                logging.warning("exception: %s" % e)
            else:
                self._conn.close()
                self._conn = _new_conn
                self._conn.set_character_set("utf8")

    def cursor(self):
        """return cursor object"""
        cursor = self._conn.cursor()
        cursor.execute('SET NAMES utf8;')
        cursor.execute('SET CHARACTER SET utf8;')
        cursor.execute('SET character_set_connection=utf8;')
        cursor.execute("SET AUTOCOMMIT=1;")
        return cursor

    def cursor2(self):
        """return cursor object"""
        cursor = self._conn.cursor()
        cursor.execute('SET NAMES utf8;')
        cursor.execute('SET CHARACTER SET utf8;')
        cursor.execute('SET character_set_connection=utf8;')
        cursor.execute('start transaction')
        return cursor

    def __enter__(self, *args, **kwargs):
        """entry transaction"""
        return self._conn.__enter__(*args, **kwargs);

    def __exit__(self, *args, **kwargs):
        """exit transaction"""
        return self._conn.__exit__(*args, **kwargs);

    def commit(self):
        """commit transaction"""
        self._conn.commit();

    def rollback(self):
        '''rollback transatcion'''
        self._conn.rollback()

    def close(self):
        """close the connection to database"""
        self._conn.close()

    def set_character_set(self, codetype):
        self._conn.set_character_set(codetype)
