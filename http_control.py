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
import sys, datetime
__version__ = '0.0'

def debug(*objs):
	# thanks http://stackoverflow.com/a/14981125
	print('DEBUG: %s\n' % datetime.datetime.now(), *objs, file=sys.stderr)

class Server():
	supported_types = [bool, int, long, float, complex, str, unicode, tuple, list, dict]
	_type_not_implemented_msg = '''
 {0} not supported.
 You will need to manually convert it to and from one of: 
 \t%s
''' % '\n\t'.join([str(t) for t in supported_types])
	
	def __init__(self):
		pass
	def start(self):
		pass
	def stop(self):
		pass
	
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
		if type_ not in self.supported_types:
			raise NotImplementedError(self._type_not_implemented_msg.format(type_))
	
	def unregister(self, name):
		pass
	def get(self, name):
		pass
	

def demo():
	import time
	debug('http_control version %s' % __version__)
	running = True
	msg = 'you can register before or after starting the server'
	http_control_server = Server()
	http_control_server.register('running', running, bool)
	http_control_server.start()
	http_control_server.register('msg', msg, str)
	while running:
		time.sleep(0.1)
		msg = http_control_server.get('msg')
		running = http_control_server.get('running')
	http_control_server.stop()
	
if __name__ == '__main__':
	demo()
