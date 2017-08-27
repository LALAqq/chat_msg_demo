# -*- coding: utf-8 -*-
import redis
import logging
import utils.connection_pool as connection_pool
import datetime
import uuid
import time

SQL_ADD_CONTACTS    =  "insert ignore into user_contacts(`user_id`, `contacts_id`, `last_read_time`) values (%s, %s, %s);"
SQL_DEL_CONTACTS    =  "delete from user_contacts where user_id = %s and contacts_id = %s;"
SQL_GET_USER_CONTACTS = "select user_id, contacts_id, unread_msg_cnt from user_contacts where user_id = %s;"
SQL_GET_MSG = "select msg_id, sender_id, receiver_id, send_time, msg_content, status from msg_record where sender_id = %s and receiver_id = %s UNION select msg_id, sender_id, receiver_id, send_time, msg_content, status from msg_record where sender_id = %s and receiver_id = %s order by send_time "
SQL_UPDATE_MSG_STATUS = "update msg_record set status = 1 where sender_id = %s and receiver_id = %s;"
SQL_UPDATE_UNREAD_CNT = "update user_contacts set unread_msg_cnt = 0, last_read_time = %s where user_id = %s and contacts_id = %s;"
SQL_SEND_MSG = "insert ignore into msg_record(`msg_id`, `sender_id`, `receiver_id`, `msg_content`) values (%s, %s, %s, %s);"
SQL_GET_MSG_STATUS = "select status from msg_record where sender_id = %s and receiver_id = %s and msg_id = %s;"
SQL_REDUCE_UNREAD_MSG_CNT = "update user_contacts set unread_msg_cnt = unread_msg_cnt - 1 where user_id = %s and contacts_id = %s;"
SQL_ADD_UNREAD_MSG_CNT = "update user_contacts set unread_msg_cnt = unread_msg_cnt + 1 where user_id = %s and contacts_id = %s;"
SQL_DELETE_MSG = "delete from msg_record where msg_id = %s;"

class DBController(object):
    def __init__(self, config):
        self.conn_pool = connection_pool.ConnectionPool(**config['db_info'])
        self.red = redis.Redis(connection_pool = redis.ConnectionPool(host = config["redis_cache"]["host"], port = config["redis_cache"]["port"], db = config["redis_cache"]["db"]))

    
    def add_contacts(self, user_id, contacts_id):
        """
        添加联系人关系
        """
        conn = self.conn_pool.connect()
        cur = conn.cursor() 
        try:
            assert user_id != contacts_id
            cur.execute(SQL_ADD_CONTACTS, (user_id, contacts_id, time.strftime("%Y-%m-%d %H:%M:%S")))
            return True
        except:
            return False


    def delete_contacts(self, user_id, contacts_id):
        """
        删除联系人关系
        """
        conn = self.conn_pool.connect()
        cur = conn.cursor()
        cur.execute(SQL_DEL_CONTACTS, (user_id, contacts_id))
        conn.commit()
        return True

    def get_contacts(self, user_id):
        """
        获取联系人列表和未读消息数目
        """
        conn = self.conn_pool.connect()
        cur  = conn.cursor2()   
        cur.execute(SQL_GET_USER_CONTACTS, (user_id,))
        ret = []
        for row in cur.fetchall():
            uid, cid, unread = row
            ret.append({"contacts_id": cid, "no_read_msg": unread})
        return ret

    def get_msg(self, user_id, contacts_id):
        """
        获取消息列表 
        """
        conn = self.conn_pool.connect()
        ret = []
        try:
            cur  = conn.cursor2()
            cur.execute(SQL_UPDATE_UNREAD_CNT, (time.strftime("%Y-%m-%d %H:%M:%S"), user_id, contacts_id))
            cur.execute(SQL_UPDATE_MSG_STATUS, (contacts_id, user_id))
            cur.execute(SQL_GET_MSG, (user_id, contacts_id, contacts_id, user_id))
            for row in cur.fetchall():
                msg_id, sender_id, receiver_id, send_time, msg_content, status = row
                ret.append({
                    "msg_id": msg_id, 
                    "sender_id": sender_id, 
                    "receiver_id": receiver_id, 
                    "send_time": send_time.strftime("%Y-%m-%d %H:%M:%S"), 
                    "msg_content": msg_content, 
                    "status":["unread", "read"][status]})
            conn.commit()
        except Exception, e:
            conn.rollback()
        return ret

    def send_msg(self, msg_id, sender_id, receiver_id, msg_content):
        """
        发送消息，如果有必要，则反向添加联系人关系，并且更新未读消息数
        """
        conn = self.conn_pool.connect()
        try:
            cur  = conn.cursor2()
            cur.execute(SQL_ADD_CONTACTS, (receiver_id, sender_id, time.strftime("%Y-%m-%d %H:%M:%S")))
            cur.execute(SQL_SEND_MSG, (msg_id, sender_id, receiver_id, msg_content))
            cur.execute(SQL_ADD_UNREAD_MSG_CNT, (receiver_id, sender_id))
            conn.commit()
            return True
        except Exception,e:
            conn.rollback()
        return False

    def delete_msg(self, msg_id, sender_id, receiver_id):
        """ 
        删除消息,并更新未读消息数目
        """
        conn = self.conn_pool.connect()
        try:
            cur  = conn.cursor2()
            cur.execute(SQL_GET_MSG_STATUS, (sender_id, receiver_id, msg_id))
            assert cur.rowcount == 1
            status = cur.fetchone()[0]
            if not status:
                cur.execute(SQL_REDUCE_UNREAD_MSG_CNT, (receiver_id, sender_id))
            cur.execute(SQL_DELETE_MSG, (msg_id,))
            conn.commit()
            return True
        except Exception,e:
            conn.rollback()
        return False
