#import greenlet
import time
import functools
import json
import gettext
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import threading
import signal
from pika import adapters
import pika
import logging
import uuid
import collections

"""
    settings  = {
    'service_name': "rabbit_http",
    'amqp_url': 'amqp://guest:guest@127.0.0.1:5672',
    }
"""

def install():
    ioloop = tornado.ioloop.IOLoop()
    ioloop.install()

class RabMQSender(object):

    def __init__(self, amqp_url, ioloop, service_name):
        self._connection    = None
        self._channel       = None
        self._closing       = False
        self._consumer_tag  = None
        self._url           = amqp_url
#        self.loop_greenlet  = ioloop.loop_greenlet
        self.call_back_map  = {}
        self.ioloop         = ioloop
        self.service_name   = service_name
        self.EXCHANGE       = service_name
        self.ROUTING_KEY    = service_name 
        self.QUEUE          = service_name
        self.EXCHANGE_TYPE  = 'fanout'

    def connect(self):
        return adapters.TornadoConnection(pika.URLParameters(self._url),
                                          self.on_connection_open,
                                          custom_ioloop = self.ioloop)

    def close_connection(self):
        self._connection.close()

    def add_on_connection_close_callback(self):
        self._connection.add_on_close_callback(self.on_connection_closed)

    def on_connection_closed(self, connection, reply_code, reply_text):
        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            self._connection.add_timeout(5, self.reconnect)

    def on_connection_open(self, unused_connection):
        self.add_on_connection_close_callback()
        self.open_channel()

    def reconnect(self):
        if not self._closing:
            self._connection = self.connect()

    def add_on_channel_close_callback(self):
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reply_code, reply_text):
        self._connection.close()

    def on_channel_open(self, channel):
        self._channel = channel
        self.add_on_channel_close_callback()
        self.setup_exchange(self.EXCHANGE)

    def setup_exchange(self, exchange_name):
        self._channel.exchange_declare(self.on_exchange_declareok,
                                       exchange_name,
                                       self.EXCHANGE_TYPE)

    def on_exchange_declareok(self, unused_frame):
        self.setup_queue(self.QUEUE)

    def setup_queue(self, queue_name):
        self._channel.queue_declare(self.on_queue_declareok, queue_name)

    def on_queue_declareok(self, method_frame):
        self._channel.queue_bind(self.on_bindok, self.QUEUE,
                                 self.EXCHANGE, self.ROUTING_KEY)

    def add_on_cancel_callback(self):
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

    def on_consumer_cancelled(self, method_frame):
        if self._channel:
            self._channel.close()

    def acknowledge_message(self, delivery_tag):
        self._channel.basic_ack(delivery_tag)

    def on_data(self, body):
        pass

    def on_message(self, unused_channel, basic_deliver, properties, body):
#        self.acknowledge_message(basic_deliver.delivery_tag)
        self.on_data(body)
#        if properties.correlation_id in self.call_back_map:
#            call = self.call_back_map[properties.correlation_id]
#            call(body)

    def on_cancelok(self, unused_frame):
        self.close_channel()

    def stop_consuming(self):
        if self._channel:
            self._channel.basic_cancel(self.on_cancelok, self._consumer_tag)

    def start_consuming(self):
        self.add_on_cancel_callback()
        self._consumer_tag = self._channel.basic_consume(self.on_message,
                                                         self.QUEUE)

    def on_bindok(self, unused_frame):
        self.start_consuming()

    def close_channel(self):
        self._channel.close()

    def open_channel(self):
        self._connection.channel(on_open_callback=self.on_channel_open)

    def stop(self):
        self._closing = True
        self.stop_consuming()
        self._connection.ioloop.start()


#    def _send_call(self, glt, service_name, message):
#        correlation_id = str(uuid.uuid4())
#        body = json.dumps(message, encoding = 'utf-8', ensure_ascii = False)
#        self._channel.basic_publish(exchange=service_name,
#                    routing_key = service_name + '.',
#                    properties=pika.BasicProperties(
#                        reply_to = self.QUEUE,
#                        correlation_id = correlation_id),
#                    body=body)
#
#        def call_back(ret):
#            glt.switch(ret)
#
#        self.call_back_map[correlation_id] = call_back
#        ret = self.loop_greenlet.switch()
#        return ret
#        msg = json.loads(body)
        

    def send_message(self, module, body):
        body = {'msg_type': 'message', 'sender': self.service_name, 'msg_content': body}
        msg = json.dumps(body, encoding = 'utf-8', ensure_ascii = False)
        self._channel.basic_publish(exchange=module,
                    routing_key = module,
                    body=msg)

    def run(self):
        self._connection = self.connect()

class Application(tornado.web.Application):
    def __init__(self, handlers=None, default_host="", transforms=None, wsgi=False, **settings):
        tornado.web.Application.__init__(self, handlers, default_host, transforms, wsgi, **settings)
        io_loop = tornado.ioloop.IOLoop.instance()
        self.service = settings['msg_service']
        self.service.run()

    def stop(self):
        self.service.stop()

class RequestHandler(tornado.web.RequestHandler):
    def __init__(self, application, request, **kwargs):
        tornado.web.RequestHandler.__init__(self, application, request, **kwargs)
        self.send_message = application.service.send_message
        

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def __init__(self, application, request, **kwargs):
        tornado.websocket.WebSocketHandler.__init__(self, application, request, **kwargs)
        self.send_message = application.service.send_message
        self.service      = application.service
