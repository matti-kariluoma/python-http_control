#!/usr/bin/env python
# coding: ascii
'''
http_control allows an existing application to .register() state 
variables to be exposed to clients over HTTP + HTML. The HTML is 
automatically generated from the number and type of registered state 
variables.

This module keeps track of a reference to the application's state 
variables, but only accesses them in a read-only manner.

After .start() is called, an http server is started in a thread. A
web browser may then visit this server and provide new values for
the application's registered state variables.

It is the application's responsibility to use the .get() interface
to update its own internal state. This module will never attempt to
write to any of the registered state variables.

:copyright: 2014 Matti Kariluoma <matti@kariluo.ma>
:license: MIT @see LICENSE
'''
from __future__ import print_function
import sys, datetime, threading
if sys.version.startswith('3'):
	from urllib.parse import parse_qs
	from http.server import BaseHTTPRequestHandler, HTTPServer
else:
	from urlparse import parse_qs
	from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import cgi
__version__ = '0.0'

def debug(*objs):
	# thanks http://stackoverflow.com/a/14981125
	print('DEBUG: %s\n' % datetime.datetime.now(), *objs, file=sys.stderr)

def info(*objs):
	print('INFO: %s\n' % datetime.datetime.now(), *objs, file=sys.stderr)

def warning(*objs):
	# TODO: put warning messages onto web interface too
	print('WARN: %s\n' % datetime.datetime.now(), *objs, file=sys.stderr)

class Handler(BaseHTTPRequestHandler):
	supported_types = [bool, int, long, float, complex, str, unicode, tuple, list, dict]
	_type_not_implemented_msg = '''
 {0} not supported.
 You will need to manually convert it to and from one of: 
 \t%s
''' % '\n\t'.join([str(t) for t in supported_types])
	
	_text_input = '''<label for='{name}'>{name}</label>
<input type='text' name='{name}'></input>
'''
	_html_form = '''<html><body>
<form method='POST'>
{inputs}
<input type='submit'></input>
</form>
</body></html>'''
	
	@classmethod
	def _set_state(cls, registry):
		'''
		Sets the state of this class. All future instantiations (i.e.
		future HTTP requests) will reference this state.
		'''
		cls.registry = registry
	
	def do_GET(self):
		self.send_response(200)
		self.send_header('Content-type', 'text/html')
		self.end_headers()
		inputs = []
		# agghh! how are we going to pass state from the server down to here?
		for (name, (object_, type_)) in sorted(Handler.registry.items()):
			inputs.append(Handler._text_input.format(name=name))
		self.wfile.write(Handler._html_form.format(inputs=''.join(inputs)))
		 
	def _parse_POST(self):
		# thanks http://stackoverflow.com/a/13330449
		ctype, pdict = cgi.parse_header(self.headers['content-type'])
		if ctype == 'multipart/form-data':
			post = cgi.parse_multipart(self.rfile, pdict)
		elif ctype == 'application/x-www-form-urlencoded':
			length = int(self.headers['content-length'])
			post = parse_qs(self.rfile.read(length), keep_blank_values=1)
		else:
			post = {}
		return post

	def do_POST(self):
		post = self._parse_POST()
		self.send_response(200)
		self.send_header('Content-type', 'text/html')
		self.end_headers()
		self.wfile.write('''<html><body>{0}</body></html>'''.format(str(post)))

class _httpd_Thread(threading.Thread):
	def __init__(self, *args, **kwargs):
		self.host = kwargs.pop('host')
		self.port = kwargs.pop('port')
		self.handler = kwargs.pop('handler')
		self.running = True
		super(_httpd_Thread, self).__init__(*args, **kwargs)
		self.httpd = HTTPServer((self.host, self.port), self.handler)
		info('Bound to ', (self.host, self.port))
		
	def run(self):
		while self.running:
			self.httpd.handle_request()
		self.httpd.socket.close()

class Server():
	def __init__(self, host='0.0.0.0', port=8080, request_handler=None):
		'''
		'request_handler' must not be used in multiple instances of 
		Server, or else they will overwrite each others state!
		
		host: The host to allow connections addressed to, or 0.0.0.0 for any
		port: Port to listen on
		request_handler: A subclass of Handler
		'''
		self.host = host
		self.port = port
		if request_handler is None:
			# create a new derived class
			unique_name = 'Handler_%s' % datetime.datetime.now()
			unique_name = unique_name.replace(' ', '_')
			self.request_handler = type(unique_name, (Handler, object), {})
			debug('New Handler created: ', self.request_handler)
		else:
			self.request_handler = request_handler
		self.registry = {}
		self.isServing = True
	
	def start(self):
		Handler._set_state(self.registry) # pass reference
		self.httpd = _httpd_Thread(host=self.host, port=self.port, handler=self.request_handler)
		self.httpd.start()
	
	def stop(self):
		self.httpd.running = False
		# TODO: trigger handle_request()
		self.httpd = None
	
	def register(self, name, object_, type_=None):
		'''
		register a state variable with this server.
		
		name : the handle of the object, used for later .get() calls
		object_ : the python object you want to remotely control
		type_ : the type of object (only affects html generation)
				e.g. bool, int, float, str, list, dict
		'''
		if type_ is None:
			type_ = type(object_)
		if type_ not in self.request_handler.supported_types:
			raise NotImplementedError(self.request_handler._type_not_implemented_msg.format(type_))
		if name in self.registry:
			warning('{name} already registered! Overwriting {name}.'.format(name=name))
		# TODO: test/ensure object_ is stored as a reference
		self.registry[name] = (object_, type_)
	
	def unregister(self, name):
		if name in self.registry:
			del self.registry[name]
		else:
			warning('''{name} isn't registered! Not able to unregister {name}.'''.format(name=name))
	
	def get(self, name):
		if name in self.registry:
			(object_, type_) = self.registry[name]
			return object_
		else:
			warning('''{name} isn't registered! Returning None.'''.format(name=name))
			return None

def demo():
	import time
	debug('http_control version %s' % __version__)
	running = True
	msg = 'you can register before or after starting the server'
	http_control_server = Server()
	http_control_server.register('running', running, bool)
	http_control_server.start()
	debug('are we threaded?')
	http_control_server.register('msg', msg, str)
	while running:
		time.sleep(0.1)
		msg = http_control_server.get('msg')
		running = http_control_server.get('running')
		debug('msg: ', msg, '\nrunning: ', running)
	http_control_server.stop()
	
if __name__ == '__main__':
	demo()
