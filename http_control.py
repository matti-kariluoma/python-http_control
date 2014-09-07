#!/usr/bin/env python
# coding: utf-8
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
from __future__ import print_function, unicode_literals
import sys, datetime, threading, copy
if sys.version.startswith('3'):
	from urllib.parse import parse_qs
	from http.server import BaseHTTPRequestHandler, HTTPServer
	from http.client import HTTPConnection
	import io as StringIO
	long = int
	unicode = str
else:
	from urlparse import parse_qs
	from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
	from httplib import HTTPConnection
	import StringIO
import cgi
try:
	import zeroconf
	import netifaces
	import socket # only needed if zeroconf imports correctly
except ImportError:
	zeroconf = None
	netifaces = None

__version__ = '0.5'

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
	supported_types = [bool, int, long, float, str, unicode]
	_type_not_implemented_msg = '''
 {0} not supported.
 You will need to manually convert it to and from one of: 
 \t%s
''' % '\n\t'.join([str(t) for t in supported_types])
	
	_label = '''<p>Current value for "{name}": {actual_value}</p>
<p>Most recent entered value for "{name}": {our_value}</p>
<p><label for='{name}'>Enter a new value for "{name}": </label></p>
'''
	_text_input = '''<p><input type='text' name='{name}'></input></p>
'''
	_checkbox_input = '''<p><input type='checkbox' name='{name}' {checked}></input></p>
'''
	_int_input = '''<p><input type='number' name='{name}' step='1'></input></p>
'''
	# thanks http://blog.isotoma.com/2012/03/html5-input-typenumber-and-decimalsfloats-in-chrome/
	_float_input = '''<p><input type='number' name='{name}' step='any'></input></p>
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
	def _last_contacted(cls, last_contacted):
		cls.last_contacted = last_contacted
	
	@classmethod
	def set_updated(cls, updated):
		cls._updated = updated
	
	@classmethod
	def updated(cls):
		if cls._updated:
			cls._updated = False
			return True
		else:
			return False

	def _create_form(self):
		cls = self.__class__
		inputs = []
		for (name, (object_, type_, copy_)) in sorted(cls.registry.items()):
			if type_ in (int, long, float, str, unicode):
				inputs.append(cls._label.format(
						name=name,
						actual_value=unicode(object_), 
						our_value=unicode(copy_)
					))
				inputs.append(cls._text_input.format(name=name))
			elif type_ is bool:
				checked = ''
				if bool(object_):
					checked = 'checked'
				inputs.append(cls._label.format(
						name=name,
						actual_value=unicode(object_), 
						our_value=unicode(copy_)
					))
				inputs.append(cls._checkbox_input.format(
						name=name,
						checked=checked
					))
			else:
				raise NotImplementedError(cls._type_not_implemented_msg.format(type_))
		return cls._html_form.format(inputs=''.join(inputs))
	
	def _write(self, text):
		self.wfile.write(text.encode('utf-16'))
	
	def do_GET(self):
		if self.path != '/':
			self.send_response(301)
			self.send_header('Location', '/')
			self.end_headers()
		else:
			self.send_response(200)
			self.send_header('Content-type', 'text/html')
			self.end_headers()
			cls = self.__class__
			self._write(cls._html_page.format(
					form=self._create_form(), 
					contact='{0} seconds ago ({1})'.format(
							(datetime.datetime.now() - cls.last_contacted).seconds,
							self.last_contacted
						),
					messages=''.join(['<p>{0}</p>'.format(msg) for msg in cls.messages])
				))
		 
	def _parse_POST(self):
		# thanks http://stackoverflow.com/a/13330449
		ctype, pdict = cgi.parse_header(self.headers['content-type'])
		if ctype == 'multipart/form-data':
			post = cgi.parse_multipart(self.rfile, pdict)
		elif ctype == 'application/x-www-form-urlencoded':
			length = int(self.headers['content-length'])
			try:
				post = parse_qs(self.rfile.read(length), keep_blank_values=False)
			except UnicodeEncodeError:
				# jesus christ python 3, get your shit together
				warning('''sorry, can't use unicode and python3. Try again with python2.''')
				raise
		else:
			post = {}
		return post

	def do_POST(self):
		cls = self.__class__
		cls.set_updated(True)
		post = self._parse_POST()
		for (name, (object_, type_, copy_)) in sorted(cls.registry.items()):
			if type_ in (int, long, float, str, unicode):
				if name in post:
					list_ = post[name]
					str_ = list_[-1].decode('utf-8')
					if not sys.version.startswith('3') and type_ is str:
						str_ = str_.encode('ascii', 'replace')
					if str_ != '':
						cls.registry[name] = (object_, type_, type_(str_))
			elif type_ is bool:
				if name in post:
					cls.registry[name] = (object_, type_, type_(True))
				else:
					cls.registry[name] = (object_, type_, type_(False))
			else:
				raise NotImplementedError(cls._type_not_implemented_msg.format(type_))
			
		self.send_response(303)
		self.send_header('Location', '/')
		self.end_headers()
		# TODO: silly, dirty hack to make the webpage reflect current state, pls remove
		import time
		time.sleep(0.2)

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
	def __init__(
			self, 
			host='0.0.0.0', 
			port=8080, 
			request_handler=None, 
			zeroconf_disabled=False, 
			service_name=None
		):
		'''
		'request_handler' must not be used in multiple instances of 
		Server, or else they will overwrite each others state!
		
		host: The host to allow connections addressed to, or 0.0.0.0 for any
		port: Port to listen on
		request_handler: A subclass of Handler
		zeroconf_disabled: when True, disables zeroconf feature
		service_name: user-friendly name to display when using zeroconf 
				service autodiscovery
		'''
		self.host = host
		self.port = port
		now = datetime.datetime.now()
		if request_handler is None:
			# create a new derived class
			unique_name = 'Handler_%s' % now 
			unique_name = unique_name.replace(' ', '_')
			self.request_handler = type(str(unique_name), (Handler, object), {})
			debug('New Handler created: ', self.request_handler)
		else:
			self.request_handler = request_handler
		self.zeroconf_disabled = zeroconf_disabled
		if service_name is None:
			self.service_name = 'http_control_%s' % now
			self.service_name = self.service_name.replace(' ', '_')
		else:
			self.service_name = service_name
		self.registry = {}
		self.messages = []
		self.request_handler.set_updated(False)
	
	def warning(self, *objs):
		# TODO: don't display the same error over and over again
		msg = _warning(*objs)
		self.messages.append(msg)
		if len(self.messages) > self.__class__.messages_max_length:
			self.messages.pop(0) # remove oldest
	
	def updated(self):
		return self.request_handler.updated()
	
	def _get_address(self, force_local_ip):
		if not netifaces:
			return None
		interfaces = netifaces.interfaces()
		ips = []
		for iface in interfaces:
			if netifaces.AF_INET in netifaces.ifaddresses(iface):
				for address in netifaces.ifaddresses(iface)[netifaces.AF_INET]:
					if 'addr' in address:
						ip = address['addr']
						if ip.startswith('127'):
							continue
						if force_local_ip and not (
								ip.startswith('10') or
								ip.startswith('172.16') or
								ip.startswith('192.168')
							):
							continue		
						ips.append(ip)
		if ips:
			return socket.inet_aton(ips[-1])
		return None	
	
	def start(self, force_local_ip=True):
		'''
		force_local_ip: if zeroconf enabled, forces the use of a local ip
				address when advertising this service ( 192.168.x , 172.16.x, 
				or 10.x )
		'''
		self.request_handler._set_state(self.registry, self.messages) # pass reference
		self.request_handler._last_contacted(datetime.datetime.now())
		self.httpd = _httpd_Thread(host=self.host, port=self.port, handler=self.request_handler)
		self.httpd.start()
		if not zeroconf or self.zeroconf_disabled:
			info('python-zeroconf not found, or disabled! Unable to configure network autodiscovery.')
			self.zeroconf = None
		else:
			self.service_info = zeroconf.ServiceInfo(
					"_http._tcp.local.",
					"{0}._http._tcp.local.".format(self.service_name),
					address=self._get_address(force_local_ip),
					port=self.port,
					properties={'path': '/'}
				)
			self.zeroconf = zeroconf.Zeroconf()
			try:
				self.zeroconf.registerService(self.service_info)
			except AssertionError as e:
				debug(e)
	
	def stop(self):
		self.httpd.running = False
		# trigger handle_request()
		try:
			connection = HTTPConnection('127.0.0.1', self.port, timeout=1)
			connection.request('HEAD', '/')
			_ = connection.getresponse()
		except:
			pass
		self.httpd = None
		if not self.zeroconf_disabled and self.zeroconf:
			try:
				self.zeroconf.unregisterService(self.service_info)
				self.zeroconf.close()
			except:
				pass
			self.zeroconf = None
	
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
		self.request_handler._last_contacted(datetime.datetime.now())
		if name in self.registry:
			(object_, type_, copy_) = self.registry[name]
			return copy_
		else:
			self.warning('''{name} isn't registered! Returning None.'''.format(name=name))
			return None
	
	def get(self, name):
		'''
		A convenience wrapper for 'get_internal_copy'.
		
		Fetches the value of 'name', registers it, then returns the value.
		'''
		copy_ = self.get_internal_copy(name)
		if copy_ is not None:
			self.register(name, copy_)
		return copy_

def demo():
	import time
	debug('http_control version %s' % __version__)
	running = True
	read_only = 'the server will copy your data, but only you can overwrite it'
	msg = str('you can register before or after starting the server')
	umsg = unicode('les derrières')
	i = 0
	l = long(1)
	f = 2.0
	http_control_server = Server()
	http_control_server.register('running', running)
	http_control_server.register('read_only', read_only)
	http_control_server.start()
	debug('are we threaded?')
	http_control_server.register('msg', msg)
	http_control_server.register('umsg', umsg)
	http_control_server.register('i', i)
	http_control_server.register('l', l)
	http_control_server.register('f', f)
	http_control_server.warning('example warning')
	try:
		while running:
			time.sleep(0.1)
			running = http_control_server.get('running')
			_  = http_control_server.get_internal_copy('read_only')
			msg = http_control_server.get('msg')
			umsg = http_control_server.get('umsg')
			i = http_control_server.get('i')
			l = http_control_server.get('l')
			f = http_control_server.get('f')
		debug('msg: ', msg, '\nread_only: ', read_only, '\nrunning: ', running)
	except KeyboardInterrupt:
		pass
	finally:
		http_control_server.stop()
	
if __name__ == '__main__':
	demo()
