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
import sys, datetime, threading, copy, StringIO
if sys.version.startswith('3'):
	from urllib.parse import parse_qs
	from http.server import BaseHTTPRequestHandler, HTTPServer
	from http.client import HTTPConnection
else:
	from urlparse import parse_qs
	from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
	from httplib import HTTPConnection
import cgi
__version__ = '0.1'

def debug(*objs):
	# thanks http://stackoverflow.com/a/14981125
	print('DEBUG: %s\n' % datetime.datetime.now(), *objs, file=sys.stderr)

def info(*objs):
	print('INFO: %s\n' % datetime.datetime.now(), *objs, file=sys.stderr)

def _warning(*objs):
	str_buf = StringIO.StringIO()
	print('WARN: %s\n' % datetime.datetime.now(), *objs, file=str_buf)
	msg = str_buf.getvalue()
	str_buf.close()
	print(msg, file=sys.stderr)
	return msg

class Handler(BaseHTTPRequestHandler):
	supported_types = [bool, int, long, float, complex, str, unicode, tuple, list, dict]
	_type_not_implemented_msg = '''
 {0} not supported.
 You will need to manually convert it to and from one of: 
 \t%s
''' % '\n\t'.join([str(t) for t in supported_types])
	
	_text_input = '''<p><label for='{name}'>{name}: {value}</label></p>
<p><input type='text' name='{name}'></input></p>
'''
	_html_form = '''<form method='POST'>
{inputs}
<p><input type='submit'></input></p>
</form>
'''
	_html_page = '''<html><body>
{form}
<p>Last system contact: {contact}</p>
<p>System messages:</p>
<p>{messages}</p>
</body></html>'''
	@classmethod
	def _set_state(cls, registry, messages):
		'''
		Sets the state of this class. All future instantiations (i.e.
		future HTTP requests) will reference this state.
		'''
		cls.registry = registry
		cls.messages = messages
	@classmethod
	def _last_contacted_msg(cls, last_contacted_msg):
		cls.last_contacted_msg = last_contacted_msg
		
	def _create_form(self):
		cls = self.__class__
		inputs = []
		for (name, (object_, type_, copy_)) in sorted(cls.registry.items()):
			inputs.append(Handler._text_input.format(name=name, value=str(object_)))
		return cls._html_form.format(inputs=''.join(inputs))
	
	def do_GET(self):
		cls = self.__class__
		self.send_response(200)
		self.send_header('Content-type', 'text/html')
		self.end_headers()
		self.wfile.write(cls._html_page.format(
				form=self._create_form(), 
				contact=cls.last_contacted_msg,
				messages=''.join(['<p>{0}</p>'.format(msg) for msg in cls.messages])
			))
		 
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
		cls = self.__class__
		post = self._parse_POST()
		self.send_response(200)
		self.send_header('Content-type', 'text/html')
		self.end_headers()
		for (name, list_) in post.items():
			if name in cls.registry:
				(object_, type_, copy_) = cls.registry[name]
				# TODO: this will need to get more complex!
				str_ = list_[0]
				cls.registry[name] = (object_, type_, type_(str_))
			else:
				debug('{name} found in POST, but {name} not registered!'.format(name=name))
		self.wfile.write('''<html><body>POST: {0}{1}</body></html>'''.format(str(post), self._create_form()))

class _httpd_Thread(threading.Thread):
	def __init__(self, *args, **kwargs):
		host = kwargs.pop('host')
		port = kwargs.pop('port')
		handler = kwargs.pop('handler')
		self.running = True
		super(_httpd_Thread, self).__init__(*args, **kwargs)
		info('Attempting to bind: ', (host, port))
		self.httpd = HTTPServer((host, port), handler)
		
	def run(self):
		while self.running:
			self.httpd.handle_request()
		self.httpd.socket.close()

class Server():
	messages_max_length = 255
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
		self.messages = []
		self.last_contacted = datetime.datetime.now()
		self.isServing = True
	
	def warning(self, *objs):
		# TODO: don't display the same error over and over again
		msg = _warning(*objs)
		self.messages.append(msg)
		if len(self.messages) > self.__class__.messages_max_length:
			self.messages.pop(0) # remove oldest
	
	def start(self):
		Handler._set_state(self.registry, self.messages) # pass reference
		self.httpd = _httpd_Thread(host=self.host, port=self.port, handler=self.request_handler)
		self.httpd.start()
	
	def stop(self):
		self.httpd.running = False
		# trigger handle_request()
		connection = HTTPConnection('127.0.0.1', self.port, timeout=1)
		connection.request('HEAD', '/')
		_ = connection.getresponse()
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
		# TODO: test/ensure object_ is stored as a reference
		# TODO: consider a class for registry objects, rather than tuples
		self.registry[name] = (object_, type_, copy.deepcopy(object_))
	
	def unregister(self, name):
		if name in self.registry:
			del self.registry[name]
		else:
			self.warning('''{name} isn't registered! Not able to unregister {name}.'''.format(name=name))
	
	def get_internal_copy(self, name):
		'''
		fetch the (possibly updated) value of 'name'.
		
		if using the pattern:
				val = this.get_internal_copy("val")
		please note that you have overwritten your application's reference
		to `val'. You will then need to call
				this.register('val', val)
		This 'get and set' pattern is provided in the convienence function 'get'
		'''
		now = datetime.datetime.now()
		# TODO: replace this with client-side javascript to do the math,
		# TODO: it freezes at "0 seconds ago" when the client app dies
		self.request_handler._last_contacted_msg('{0} seconds ago ({1})'.format(
				(now - self.last_contacted).seconds,
				self.last_contacted
			))
		self.last_contacted = now
		if name in self.registry:
			(object_, type_, copy_) = self.registry[name]
			return copy_
		else:
			self.warning('''{name} isn't registered! Returning None.'''.format(name=name))
			return None
	
	def get(self, name):
		copy_ = self.get_internal_copy(name)
		if copy_ is not None:
			self.register(name, copy_)
		return copy_

def demo():
	import time
	debug('http_control version %s' % __version__)
	running = True
	read_only = 'the server will copy your data, but only you can overwrite it'
	msg = 'you can register before or after starting the server'
	http_control_server = Server()
	http_control_server.register('running', running)
	http_control_server.register('read_only', read_only)
	http_control_server.start()
	debug('are we threaded?')
	http_control_server.register('msg', msg)
	http_control_server.warning('example warning')
	try:
		while running:
			time.sleep(0.1)
			msg = http_control_server.get('msg')
			_  = http_control_server.get_internal_copy('read_only')
			running = http_control_server.get('running')
			debug('msg: ', msg, '\read_only: ', read_only, '\nrunning: ', running)
	except KeyboardInterrupt:
		pass
	finally:
		http_control_server.stop()
	
if __name__ == '__main__':
	demo()
