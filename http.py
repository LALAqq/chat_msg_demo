# -*- coding: utf-8 -*-
import tornado.httpserver
import json
import tornado
import tornado.ioloop
import os
import tornado.web
import tornado.websocket
import controller
import uuid
from urllib import unquote
import logging

db_controller = None

contacts_ws_online = {} #保存所有在线的联系人列表websocket,用于实时更新联系人列表和未读消息数目
chats_ws_online    = {} #保存所有在线的聊天页面websocket,用于试试更新消息列表和消息读取状态

def install(config):
    global db_controller
    logging.basicConfig(level=config['log_level'],  
                        filename=config['log_file'],
                                format='[%(levelname)1.1s %(asctime)s %(filename)s :%(lineno)d] %(message)s')
    db_controller = controller.DBController(config)
    ioloop = tornado.ioloop.IOLoop()
    ioloop.install()

def verify_token(func):
    """
        对token进行验证
    """
    def wrap(handler, *args, **kwargs):
        try:
            handler.user_id = ""
            uri = unquote(handler.request.uri)
            token =  uri.split('token=')[1].split('&')[0]
            user_id = db_controller.verify_token(token)
            logging.info("user_id is:" + user_id)
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
            assert db_controller.verify_contacts(handler.user_id, contacts_id)
            handler.contacts_id = contacts_id
        except Exception, e:
            logging.error(e, exc_info = True)
            raise tornado.web.HTTPError(400)
        return func(handler, *args, **kwargs)  
    return wrap

class LoginPageHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('login.html')

class ContactsPageHandler(tornado.web.RequestHandler):

    @verify_token
    def get(self):
        self.render('contacts.html')

class ChatPageHandler(tornado.web.RequestHandler):

    @verify_token
    @verify_contacts
    def get(self):
        self.render('chat.html')

class LoginHandler(tornado.web.RequestHandler):

    def get(self):
        user_id = self.get_argument('user_name')
        passwd  = self.get_argument('passwd')
        token = db_controller.login(user_id, passwd) 
        if token == None:
            self.write(json.dumps({"error_code": 4004, "error_msg": "token invalid"}))
            return 
        self.write(json.dumps({"error_code": 2000, "token": token}))

class ContactsActionWsHandler(tornado.websocket.WebSocketHandler):
    """
        联系人列表页面的websocket,用于接收联系人查询,增加,更新操作,同时可更新联系人列表信息
    """
    @verify_token
    def check_origin(self, origin):  
        return True
  
    @verify_token
    def open(self): 
        contacts_ws_online[self.user_id] = self
  
    def on_message(self, message):  
        msg = json.loads(message) 
        action = msg['action']
        if action == 'get_contacts':
            contacts = db_controller.get_contacts(self.user_id)

        if action == 'add_contacts':
            cid = msg['contacts_id']
            db_controller.add_contacts(self.user_id, cid)
            contacts = db_controller.get_contacts(self.user_id)

        if action == 'delete_contacts':
            cid = msg['contacts_id']
            db_controller.delete_contacts(self.user_id, cid)
            contacts = db_controller.get_contacts(self.user_id)
        self.write_message(json.dumps(contacts, ensure_ascii = False))
  
    def on_close(self):
        if self.user_id in contacts_ws_online:
            del contacts_ws_online[self.user_id]

class MsgActionWsHandler(tornado.websocket.WebSocketHandler):
    """
        消息页面的websocket,用于接收消息查询,发送,删除操作,同时更新消息列表信息
    """
    def check_origin(self, origin):  
        return True
  
    @verify_token
    @verify_contacts
    def open(self):  
        group_id = self.user_id + "__" + self.contacts_id
        chats_ws_online[group_id] = self
  
    @verify_token
    @verify_contacts
    def on_message(self, message):  
        msg = json.loads(message) 
        action = msg['action']
        if action == 'get_msg':
            msg_list = db_controller.get_msg(self.user_id, self.contacts_id)

        if action == 'send_msg':
            msg_content = msg['msg_content']
            msg_id = str(uuid.uuid4())
            db_controller.send_msg(msg_id, self.user_id, self.contacts_id, msg_content)
            msg_list = db_controller.get_msg(self.user_id, self.contacts_id)

        if action == 'delete_msg':
            msg_id = msg["msg_id"]
            db_controller.delete_msg(msg_id, self.user_id, self.contacts_id)
            msg_list = db_controller.get_msg(self.user_id, self.contacts_id)

        c_group_id = self.contacts_id + "__" + self.user_id
        if c_group_id in chats_ws_online:#对方聊天页面在线，更新对方聊天信息
            cmsg_list = db_controller.get_msg(self.contacts_id, self.user_id)
            msg_list = db_controller.get_msg(self.user_id, self.contacts_id)
            try:
                chats_ws_online[c_group_id].write_message(json.dumps(cmsg_list, ensure_ascii = False))
            except:
                del chats_ws_online[c_group_id]

        if self.contacts_id in contacts_ws_online:#对方联系人页面在线，更对方新联系人列表信息
            contacts = db_controller.get_contacts(self.contacts_id)
            try:
                contacts_ws_online[self.contacts_id].write_message(json.dumps(contacts, ensure_ascii = False))
            except:
                del contacts_ws_online[self.contacts_id]

        if action == 'get_msg' and self.user_id in contacts_ws_online:#本人联系人页面在线，更新本人联系人列表信息
            contacts = db_controller.get_contacts(self.user_id)
            try:
                contacts_ws_online[self.user_id].write_message(json.dumps(contacts, ensure_ascii = False))
            except:
                del contacts_ws_online[self.user_id]


        self.write_message(json.dumps(msg_list, ensure_ascii = False))
  
    def on_close(self):
        if self.user_id in chats_ws_online:
            del chats_ws_online[self.user_id]

if __name__ == '__main__':
    config = {}
    execfile(os.path.join(os.path.dirname(__file__), './config/module.conf'), config)
    install(config)
    handlers = [
        (r'/page/login.html', LoginPageHandler),
        (r'/page/contacts.html', ContactsPageHandler),
        (r'/page/chat_msg.html', ChatPageHandler),
        (r'/msg_demo/login', LoginHandler),
        (r'/ws/ws_contacts_action', ContactsActionWsHandler),
        (r'/ws/ws_msg_action', MsgActionWsHandler),
    ]

    app = tornado.web.Application(handlers, 
            template_path = os.path.join(os.path.dirname(__file__), 'static'),
            static_path   = os.path.join(os.path.dirname(__file__), 'static'))
    server = tornado.httpserver.HTTPServer(app)
    server.listen(config["http_port"])
    io_loop = tornado.ioloop.IOLoop.current()
    io_loop.start()
