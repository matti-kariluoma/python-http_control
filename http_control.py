#!/usr/bin/env python
# coding: utf-8
'''
http_control allows an existing application to .register() state 
variables to be exposed to clients over HTTP + HTML. The HTML is 
automatically generated from the number and type of registered state 
variables.

After .start() is called, an http server is started in a thread. A
web browser may then visit this server and provide new values for
the application's registered state variables.

It is the application's responsibility to use the .get() interface
to update its own internal state.

:copyright: 2014 Matti Kariluoma <matti@kariluo.ma>
:license: MIT @see LICENSE
'''
from __future__ import print_function, unicode_literals
import sys, datetime, threading
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

__version__ = '0.9'
__debug__http_control__ = True

def _stderr(*objs):
	# thanks http://stackoverflow.com/a/14981125
	print(*objs, file=sys.stderr)

def debug(*objs):
	if __debug__http_control__:
		_stderr('DEBUG: %s\n' % datetime.datetime.now(), *objs)

def info(*objs):
	_stderr('INFO: %s\n' % datetime.datetime.now(), *objs)

class Type(object):
	def __init__(self):
		self.label = "{name} {value}"
		self.input = "{name} {value}"
	def format_object(self, object_):
		return unicode(object_)
	def format(self, name, object_):
		return (
				self.label.format(name=name, value=self.format_object(object_)), 
				self.input.format(name=name, value=self.format_object(object_))
			)

class Type_text(Type):
	def __init__(self):
		self.label = '''<h3>{name}</h3>
	<p>Last known value: {value}</p>
	<p><label for='{name}'>Enter a new value: </label>
'''
		self.input = '''	<input type='text' name='{name}' placeholder='{value}'></input></p>
'''

class Type_bool(Type_text):
	def __init__(self):
		super(Type_bool, self).__init__()
		self.input = '''	<input type='checkbox' name='{name}' {checked}></input></p>
'''
	def format_object(self, object_):
		return 'checked' if bool(object_) else ''
	def format(self, name, object_):
		return (
				self.label.format(name=name, value=unicode(object_)), 
				self.input.format(name=name, checked=self.format_object(object_))
			)

class Type_int(Type_text):
	def __init__(self):
		super(Type_int, self).__init__()
		self.input = '''	<input type='number' name='{name}' placeholder='{value}' step='1'></input></p>
'''

class Type_float(Type_text):
	def __init__(self):
		super(Type_float, self).__init__()
		# thanks http://blog.isotoma.com/2012/03/html5-input-typenumber-and-decimalsfloats-in-chrome/
		self.input = '''	<input type='number' name='{name}' placeholder='{value}' step='any'></input></p>
'''
			
class Type_list(Type):
	def __init__(self):
		self.label = '''<h3>{name}</h3>
	<p>Last known value: <textarea rows='5' readonly>{value}</textarea></p>
	<p><label for='{name}'>Enter a new value: </label>
'''
		self.input = '''	<textarea name='{name}' rows='5'>{value}</textarea>
'''
	def format(self, name, object_):
		val = '\n'.join([unicode(item) for item in object_])
		return (
				self.label.format(name=name, value=val),
				self.input.format(name=name, value=val)
			)

class Type_dict(Type):
	def __init__(self):
		self.label = '''<h3>{name}</h3>
	<p>Last known value: <textarea rows='5' readonly>{keys}</textarea>
	<textarea rows='5' readonly>{values}</textarea></p>
	<p><label for='{name}'>Enter a new value: </label>
'''
		self.input = '''	<textarea name='{name}_keys' rows='5'>{keys}</textarea>
	<textarea name='{name}_values' rows='5'>{values}</textarea>
'''
	def format_object(self, object_):
		return (
			'\n'.join(str(key) for key in object_.keys()), 
			'\n'.join(str(value) for value in object_.values())
		)
	def format(self, name, object_):
		keys, values = self.format_object(object_)
		return (
				self.label.format(name=name, keys=keys, values=values), 
				self.input.format(name=name, keys=keys, values=values)
			)

class Handler(BaseHTTPRequestHandler):
	_messages = {}
	supported_types = {
			bool: Type_bool(), 
			int: Type_int(), 
			long: Type_int(), 
			float: Type_float(), 
			str: Type_text(), 
			unicode: Type_text(), 
			tuple: Type_list(), 
			list: Type_list(), 
			dict: Type_dict(),
		}
	_escapes = [
			('&', '&apos;'), # '&'  must be first item in this list
			('<', '&lt;'),
			('>', '&gt;'),
			('"', '&quot;'),
			('\'', '&apos;'),
		]
	_type_not_implemented_msg = '''
 {0} not supported.
 You will need to manually convert it to and from one of: 
 \t%s
''' % '\n\t'.join([str(t) for t in supported_types.keys()])

	_html_form = '''<form method='POST'>
{inputs}
<p><input type='submit'></input></p>
</form>
'''
	_html_page = '''<html><body>
{form}
<p>Application last contacted: {contact}</p>
<p>System messages:</p>
<p>{messages}</p>
</body></html>'''
	
	@classmethod
	def warning(cls, *objs):
		str_buf = StringIO.StringIO()
		print('WARN: ', *objs, file=str_buf)
		msg = str_buf.getvalue()
		str_buf.close()
		_stderr(msg)
		try:
			count_time = list(cls._messages[msg])
			count_time[0] += 1
			count_time[1] = datetime.datetime.now()
			count_time = tuple(count_time)
		except KeyError:
			count_time = (1, datetime.datetime.now())
		cls._messages[msg] = count_time
	
	@classmethod
	def _set_state(cls, registry):
		'''
		Sets the state of this class. All future instantiations (i.e.
		future HTTP requests) will reference this state.
		'''
		cls.registry = registry
	
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
	
	@classmethod
	def escape(cls, s):
		'''
		cgi.escape isn't very complete
		'''
		for char_esc in cls._escapes:
			s = s.replace(char_esc[0], char_esc[1])
		return s
	
	@classmethod
	def unescape(cls, e):
		'''
		opposite of our escape func
		'''
		for char_esc in reversed(cls._escapes):
			e = e.replace(char_esc[1], char_esc[0])
		return e
		
	def _create_form(self):
		cls = self.__class__
		inputs = []
		for (name, (object_, type_)) in sorted(cls.registry.items()):
			name = cls.escape(name)
			try:
				type_to_html = cls.supported_types[type_]
			except KeyError:
				raise NotImplementedError(cls._type_not_implemented_msg.format(type_))
			inputs.extend(type_to_html.format(name, object_))
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
					messages=''.join([
							'<p>{0} {1} ({2})</p>'.format(msg, count_time[1], count_time[0]) for (msg, count_time) in sorted(
									cls._messages.items(), 
									key=lambda (msg, count_time): count_time[1] # sort by message date
								)
						]) or '(No system messages)'
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
		for (name, (object_, type_)) in sorted(cls.registry.items()):
			# TODO: implement this in the Type_* classes
			if type_ in (int, long, float, str, unicode, tuple, list, dict):
				if type_ is dict:
					post_keys = '{0}_keys'.format(name)
					post_values = '{0}_values'.format(name)
					if post_keys in post and post_values in post:
						list_ = post[post_keys]
						str_keys = list_[-1].decode('utf-8')
						list_ = post[post_values]
						str_values = list_[-1].decode('utf-8')
						keys = str_keys.split('\n')
						values = str_values.split('\n')
						cls.registry[name] = (dict(zip(keys, values)), type_)
				elif name in post:
					list_ = post[name]
					str_ = list_[-1].decode('utf-8')
					if not sys.version.startswith('3') and type_ is str:
						str_ = str_.encode('ascii', 'replace')
					if type_ in (tuple, list):
						#TODO saw wierd behaviorwhen using mobile client
						cls.registry[name] = (str_.split('\n'), type_)
					if str_ != '':
						try:
							cls.registry[name] = (type_(str_), type_)
						except ValueError as e:
							cls.warning(e)
			elif type_ is bool:
				if name in post:
					cls.registry[name] = (type_(True), type_)
				else:
					cls.registry[name] = (type_(False), type_)
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
		try:
			while self.running:
				self.httpd.handle_request()
		except:
			raise
		finally:
			self.httpd.socket.close()

class Server():
	def __init__(
			self, 
			host='0.0.0.0', 
			port=8000, 
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
		now = datetime.datetime.now().strftime('%s')
		if request_handler is None:
			# create a new derived class
			unique_name = 'Handler_%s' % now
			unique_name = unique_name.replace(' ', '_')
			self.request_handler = type(str(unique_name), (Handler, object), {})
			debug('New Handler created: ', unique_name, self.request_handler)
		else:
			self.request_handler = request_handler
		self.zeroconf_disabled = zeroconf_disabled
		if service_name is None:
			self.service_name = 'http_control_%s' % now
			self.service_name = self.service_name.replace(' ', '_')
		else:
			self.service_name = service_name
		self.registry = {}
		self.request_handler.set_updated(False)
	
	def warning(self, *objs):
		if self.request_handler:
			self.request_handler.warning(*objs)
	
	def set_debug(self, should_debug):
		global __debug__http_control__
		__debug__http_control__ = should_debug
	
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
		self.request_handler._set_state(self.registry) # pass reference
		self.request_handler._last_contacted(datetime.datetime.now())
		self.httpdt = _httpd_Thread(host=self.host, port=self.port, handler=self.request_handler)
		self.httpdt.start()
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
		self.httpdt.running = False
		# trigger handle_request()
		try:
			connection = HTTPConnection('127.0.0.1', self.port, timeout=1)
			connection.request('HEAD', '/')
			_ = connection.getresponse()
		except:
			pass
		self.httpdt = None
		if not self.zeroconf_disabled and self.zeroconf:
			try:
				self.zeroconf.unregisterService(self.service_info)
				self.zeroconf.close()
			except:
				pass
			self.zeroconf = None
	
	def register(self, name, object_, type_=None):
		'''
		Register a state variable with this server.
		
		name : the handle of the object, used for later .get() calls
		object_ : the python object you want to remotely control
		type_ : the type of object (only affects html generation)
				e.g. bool, int, float, str, list, dict
		'''
		if type_ is None:
			type_ = type(object_)
		if type_ not in self.request_handler.supported_types.keys():
			raise NotImplementedError(self.request_handler._type_not_implemented_msg.format(type_))
		self.registry[name] = (object_, type_)
	
	def unregister(self, name):
		if name in self.registry:
			del self.registry[name]
		else:
			self.warning('''{name} isn't registered! Not able to unregister {name}.'''.format(name=name))
	
	def get(self, name):
		'''
		Fetches the (possibly updated) value of 'name'
		'''
		self.request_handler._last_contacted(datetime.datetime.now())
		if name in self.registry:
			(object_, type_) = self.registry[name]
			return object_
		else:
			self.warning('''{name} isn't registered! Returning None.'''.format(name=name))
			return None

def test():
	import time
	debug('http_control version %s' % __version__)
	## parse command line
	port = None
	if len(sys.argv) > 1:
		try:
			port = int(sys.argv[1])
		except ValueError:
			port = None
	if port:
		http_control_server = Server(port=port)
	else:
		http_control_server = Server()
	http_control_server.start()
	sockname = (http_control_server.host, http_control_server.port)
	info("Serving HTTP on {0} port {1}...".format(*sockname))
	## setup Server
	running = True
	msg = "Hello world!"
	http_control_server.register('running', running)
	http_control_server.register('msg', msg)
	if __debug__http_control__:
		for type_ in http_control_server.request_handler.supported_types.keys():
			http_control_server.register(str(type_), type_())
	try:
		while running:
			running = http_control_server.get('running')
			msg = http_control_server.get('msg')
		debug('msg: ', msg, '\nrunning: ', running)
	except KeyboardInterrupt:
		pass
	finally:
		http_control_server.stop()
	return 0
	
if __name__ == '__main__':
	sys.exit(test())
