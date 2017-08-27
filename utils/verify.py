# -*- coding: utf-8 -*-
import redis
import logging
import utils.connection_pool as connection_pool
import datetime
import uuid
import time

SQL_USER_LOGIN      = "select passwd from user_info where user_id = %s;"
SQL_USER_CREATE     = "insert into user_info(`user_id`, `passwd`) values (%s, %s);"
SQL_CHECK_CONTACTS = "select user_id from user_contacts where user_id = %s and contacts_id = %s;";

class DBVerify(object):
    def __init__(self, config):
        self.conn_pool = connection_pool.ConnectionPool(**config['db_info'])
        self.red = redis.Redis(connection_pool = redis.ConnectionPool(host = config["redis_cache"]["host"], port = config["redis_cache"]["port"], db = config["redis_cache"]["db"]))

    def _create_token(self, user_id):
        """
        创建token，有效期为1小时
        """
        token = str(uuid.uuid4())
        self.red.set(token, user_id)
        self.red.expire(token, 3600)
        return token

    def verify_token(self, token):
        """
        验证token，延长有效期
        """
        user_id  = self.red.get(token)
        if user_id:
            self.red.expire(token, 3600)
            return user_id
        return None

    def login(self, user_id, passwd):
        """
        进行登录/如果没有这个user_id则进行注册
        """
        conn = self.conn_pool.connect()
        cur = conn.cursor()
        try:
            cur.execute(SQL_USER_LOGIN, (user_id,))
            if cur.rowcount == 0:
                cur.execute(SQL_USER_CREATE, (user_id, passwd))
            else:
                pw = cur.fetchone()[0]
                assert pw == passwd
            return self._create_token(user_id) 
        except Exception, e:
            return None

    def verify_contacts(self, user_id, contacts_id):
        """
        验证联系人关系，每次对消息进行操作都会先验证下
        """
        conn = self.conn_pool.connect()
        cur = conn.cursor()   
        cur.execute(SQL_CHECK_CONTACTS, (user_id, contacts_id))
        return  cur.rowcount == 1
