import pika
import pprint
import time
import logging
import json

class RabMQConsumer(object):

    def __init__(self, amqp_url, service_name):
        self._connection    = None
        self._channel       = None
        self._url           = amqp_url
        self.service_name   = service_name
        self.EXCHANGE       = service_name
        self.ROUTING_KEY    = service_name 
        self.QUEUE          = service_name
        self.EXCHANGE_TYPE  = 'topic'

    def _connect(self):
        self._connection = pika.BlockingConnection(pika.URLParameters(self._url))
        self._channel = self._connection.channel()
        self._channel.exchange_declare(exchange = self.EXCHANGE, type = self.EXCHANGE_TYPE)
        self._channel.queue_declare(queue = self.QUEUE)
        self._channel.queue_bind(self.QUEUE, self.EXCHANGE, self.ROUTING_KEY)
        self._channel.basic_consume(self._on_message, queue = self.QUEUE, no_ack = True)
        
    def start(self):
        self._connect()
        self._channel.start_consuming()
         
    def _on_message(self, ch, method, properties, body):
        try:
            msg = json.loads(body)
            msg_type = msg['msg_type']
            msg_content = msg['msg_content']
            sender = msg['sender'] 
            ret = self.on_data(sender, msg_content)
            if msg_type == 'call':
                ret_msg = {'msg_type': 'call_return', 'sender': self.service_name, 'msg_content': ret}
                correlation_id = properties.correlation_id
                self._call_back(sender, correlation_id, json.dumps(ret_msg, ensure_ascii = False))
        except Exception, e:
            logging.info(e, exc_info = True)

    def _call_back(self, service_name, correlation_id, body):
        ch.basic_publish(exchange = service_name, routing_key = service_name,
            properties = pika.BasicProperties(correlation_id = correlation_id),
            body = body)

    def on_data(self, sender, msg):
        pass

    def send_message(self, module, body):
        msg = {'msg_type': 'message', 'sender': self.service_name, 'msg_content': body}
        self._channel.basic_publish(exchange = module, routing_key = module,
            body = json.dumps(msg, ensure_ascii = False))

