import utils.controller as controller
import utils.consumer as consumer 
import os
import json
import time
import logging
import functools
import uuid

MSG_TYPE_UPDATE_CONTACTS = 'update_contacts'
MSG_TYPE_UPDATE_MSG = 'update_msg'
MSG_TYPE_TO_GET_CONTACTS = 'to_get_contacts'
MSG_TYPE_TO_GET_MSG = 'to_read_msg'

HTTP_MODULE  = 'http_module'

class DBConsumer(consumer.RabMQConsumer):

    def __init__(self, **config):
        super(DBConsumer, self).__init__(config['amqp_url'], config['service_name']) 
        self.db_controller = controller.DBController(config)
        self.send_message = functools.partial(super(DBConsumer, self).send_message, HTTP_MODULE)
    
    def on_data(self, sender, msg):
        action  = msg['action']
        user_id = str(msg['user_id'])

        if action == 'get_contacts':
            contacts = self.db_controller.get_contacts(user_id)
            self.send_message({'action':MSG_TYPE_UPDATE_CONTACTS, 'user_id': user_id,  'contacts_list': contacts})

        if action == 'add_contacts':
            cid = str(msg['contacts_id'])
            self.db_controller.add_contacts(user_id, cid)
            contacts = self.db_controller.get_contacts(user_id)
            self.send_message({'action':MSG_TYPE_UPDATE_CONTACTS, 'user_id': user_id, 'contacts_list': contacts})

        if action == 'delete_contacts':
            cid = str(msg['contacts_id'])
            self.db_controller.delete_contacts(user_id, cid)
            contacts = self.db_controller.get_contacts(user_id)
            self.send_message({'action':MSG_TYPE_UPDATE_CONTACTS, 'user_id': user_id, 'contacts_id': cid, 'msg_list': contacts})

        if action == 'get_msg':
            cid = str(msg['contacts_id'])
            msg_list = self.db_controller.get_msg(user_id, cid)
            self.send_message({'action':MSG_TYPE_UPDATE_MSG, 'user_id': user_id, 'contacts_id': cid, 'msg_list': msg_list})
            self.send_message({'action':MSG_TYPE_TO_GET_CONTACTS, 'user_id': user_id})

        if action == 'send_msg':
            cid = str(msg['contacts_id'])
            msg_id = str(uuid.uuid4())
            msg_content = msg['msg_content']
            self.db_controller.send_msg(msg_id, user_id, cid, msg_content)
            self.send_message({'action':MSG_TYPE_TO_GET_MSG, 'user_id': cid, 'contacts_id': user_id})
            self.send_message({'action':MSG_TYPE_TO_GET_CONTACTS, 'user_id': cid})
            self.send_message({'action':MSG_TYPE_TO_GET_MSG, 'user_id': user_id, 'contacts_id': cid})

        if action == 'delete_msg':
            cid = str(msg['contacts_id'])
            msg_id = msg['msg_id']
            self.db_controller.delete_msg(msg_id, user_id, cid)
            msg_list = self.db_controller.get_msg(user_id, cid)
            self.send_message({'action':MSG_TYPE_UPDATE_MSG, 'user_id': user_id, 'contacts_id': cid, 'msg_list': msg_list})
            self.send_message({'action':MSG_TYPE_TO_GET_CONTACTS, 'user_id': cid})
            self.send_message({'action':MSG_TYPE_TO_GET_MSG, 'user_id': cid, 'contacts_id': user_id})

        if action == 'read_msg':
            cid = str(msg['contacts_id'])
            msg_list = self.db_controller.get_msg(user_id, cid)
            self.send_message({'action': MSG_TYPE_UPDATE_MSG, 'user_id': user_id, 'contacts_id': cid, 'msg_list': msg_list})

def install(config):
    logging.basicConfig(level=config['log_level'],  
                        filename=config['log_file'],
                                format='[%(levelname)1.1s %(asctime)s %(filename)s :%(lineno)d] %(message)s')
    module = DBConsumer(**config)
    module.start()
     
if __name__ == '__main__':
    config = {}
    execfile(os.path.join(os.path.dirname(__file__), './config/db_module.conf'), config)
    install(config)
