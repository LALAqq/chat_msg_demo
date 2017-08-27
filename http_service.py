# -*- coding: utf-8 -*-
import tornado.httpserver
import json
import tornado
import tornado.ioloop
import os
import tornado.web
import tornado.websocket
import utils.verify as verify
import uuid
from urllib import unquote
import logging
import utils.rservice as rservice

db_verify = None


def install(config):
    global db_verify
    logging.basicConfig(level=config['log_level'],  
#                        filename=config['log_file'],
                                format='[%(levelname)1.1s %(asctime)s %(filename)s :%(lineno)d] %(message)s')
    db_verify = verify.DBVerify(config)
    ioloop = tornado.ioloop.IOLoop()
    ioloop.install()


MSG_TYPE_UPDATE_CONTACTS = 'update_contacts'
MSG_TYPE_UPDATE_MSG = 'update_msg'
MSG_TYPE_MSG_READ = 'msg_read'
MSG_TYPE_TO_GET_CONTACTS = 'to_get_contacts'
MSG_TYPE_TO_GET_MSG = 'to_read_msg'

DB_MODULE = 'db_module'

class MsgService(rservice.RabMQSender):
    def __init__(self, amqp_url, ioloop, service_name):
        super(MsgService, self).__init__(amqp_url, ioloop, service_name)
        self.contacts_ws_online = {} #保存所有在线的联系人列表websocket,用于实时更新联系人列表和未读消息数目
        self.chats_ws_online    = {} #保存所有在线的聊天页面websocket,用于试试更新消息列表和消息读取状态

    def update_contacts_info(self, uid , contacts_list):
        if uid in self.contacts_ws_online:
            ws = self.contacts_ws_online[uid]
            try:
                ws.write_message(json.dumps(contacts_list, ensure_ascii = False))
            except Exception, e:
                del self.contacts_ws_online[uid]

    def update_chat_info(self, chat_id, chat_list):
        if chat_id in self.chats_ws_online:
            ws = self.chats_ws_online[chat_id]
            try:
                ws.write_message(json.dumps(chat_list, ensure_ascii = False))
            except Exception, e:
                del self.contacts_ws_online[chat_id]

    def on_data(self, body):
        msg = json.loads(body)
        msg_content = msg['msg_content']
        action =  msg_content['action']
        if action == MSG_TYPE_UPDATE_CONTACTS:
            user_id = msg_content['user_id']
            contacts_list = msg_content['contacts_list']
            self.update_contacts_info(user_id, contacts_list)

        if action == MSG_TYPE_UPDATE_MSG:
            user_id  = msg_content['user_id']
            contacts_id = msg_content['contacts_id']
            chat_id = user_id + '__' + contacts_id
            chat_list = msg_content['msg_list']
            self.update_chat_info(chat_id, chat_list)

        if action == MSG_TYPE_TO_GET_CONTACTS:
            user_id  = msg_content['user_id']
            if user_id in self.contacts_ws_online:
                s_msg = {'action': 'get_contacts', 'user_id': user_id}
                self.send_message(DB_MODULE, s_msg)

        if action == MSG_TYPE_TO_GET_MSG:
            user_id = msg_content['user_id']
            contacts_id = msg_content['contacts_id']
            chat_id = user_id + '__' + contacts_id 
            if chat_id in self.chats_ws_online:
                s_msg = {'action': 'read_msg', 'user_id': user_id, 'contacts_id': contacts_id}
                self.send_message(DB_MODULE, s_msg)

def verify_token(func):
    """
        对token进行验证
    """
    def wrap(handler, *args, **kwargs):
        try:
            handler.user_id = ""
            uri = unquote(handler.request.uri)
            token =  uri.split('token=')[1].split('&')[0]
            user_id = db_verify.verify_token(token)
            assert  user_id != None
            handler.user_id = user_id
        except Exception, e:
            logging.error(e, exc_info = True)
            raise tornado.web.HTTPError(400)
        return func(handler, *args, **kwargs)  
    return wrap

def verify_contacts(func):
    """
        对联系人关系进行验证
    """
    def wrap(handler, *args, **kwargs):
        try:
            uri = unquote(handler.request.uri)
            contacts_id = uri.split('contacts_id=')[1].split('&')[0]
            assert db_verify.verify_contacts(handler.user_id, contacts_id)
            handler.contacts_id = contacts_id
        except Exception, e:
            logging.error(e, exc_info = True)
            raise tornado.web.HTTPError(400)
        return func(handler, *args, **kwargs)
    return wrap

class LoginPageHandler(rservice.RequestHandler):
    def get(self):
        self.render('login.html')

class ContactsPageHandler(rservice.RequestHandler):

    @verify_token
    def get(self):
        self.render('contacts.html')

class ChatPageHandler(rservice.RequestHandler):

    @verify_token
    @verify_contacts
    def get(self):
        self.render('chat.html')

class LoginHandler(rservice.RequestHandler):

    def get(self):
        user_id = self.get_argument('user_name')
        passwd  = self.get_argument('passwd')
        token = db_verify.login(user_id, passwd) 
        if token == None:
            self.write(json.dumps({"error_code": 4004, "error_msg": "token invalid"}))
            return 
        self.write(json.dumps({"error_code": 2000, "token": token}))

class ContactsActionWsHandler(rservice.WebSocketHandler):
    """
        联系人列表页面的websocket,用于接收联系人查询,增加,更新操作,同时可更新联系人列表信息
    """
    @verify_token
    def check_origin(self, origin):  
        return True
  
    @verify_token
    def open(self): 
        self.service.contacts_ws_online[self.user_id] = self
  
    def on_message(self, message):  
        msg = json.loads(message) 
        msg['user_id'] = self.user_id
        self.send_message(DB_MODULE, msg)
  
    def on_close(self):
        if self.user_id in self.service.contacts_ws_online:
            del self.service.contacts_ws_online[self.user_id]

class MsgActionWsHandler(rservice.WebSocketHandler):
    """
        消息页面的websocket,用于接收消息查询,发送,删除操作,同时更新消息列表信息
    """
    def check_origin(self, origin):  
        return True
  
    @verify_token
    @verify_contacts
    def open(self):  
        group_id = self.user_id + "__" + self.contacts_id
        self.service.chats_ws_online[group_id] = self
  
    @verify_token
    @verify_contacts
    def on_message(self, message):  
        msg = json.loads(message) 
        msg['user_id'] = self.user_id
        msg['contacts_id'] = self.contacts_id
        self.send_message(DB_MODULE, msg)
  
    def on_close(self):
        group_id = self.user_id + "__" + self.contacts_id
        if group_id in self.service.chats_ws_online:
            del self.service.chats_ws_online[group_id]

if __name__ == '__main__':
    config = {}
    execfile(os.path.join(os.path.dirname(__file__), './config/http_module.conf'), config)
    install(config)
    io_loop = tornado.ioloop.IOLoop.current()
    msg_service = MsgService(config['amqp_url'], io_loop, config['service_name'])
    handlers = [
        (r'/page/login.html', LoginPageHandler),
        (r'/page/contacts.html', ContactsPageHandler),
        (r'/page/chat_msg.html', ChatPageHandler),
        (r'/msg_demo/login', LoginHandler),
        (r'/ws/ws_contacts_action', ContactsActionWsHandler),
        (r'/ws/ws_msg_action', MsgActionWsHandler),
    ]
    app = rservice.Application(handlers, 
            template_path = os.path.join(os.path.dirname(__file__), 'static'),
            static_path   = os.path.join(os.path.dirname(__file__), 'static'),
            msg_service = msg_service)
    server = tornado.httpserver.HTTPServer(app)
    server.listen(config["http_port"])
    io_loop.start()
