#!/usr/bin/env python
# coding: utf-8
'''
http_control demo: control an OpenGL application with keyboard or http.

Setup and other bits from: 
http://code.activestate.com/recipes/325391-open-a-glut-window-and-draw-a-sphere-using-pythono/

:copyright: 2014 Matti Kariluoma <matti@kariluo.ma>
:license: MIT @see LICENSE
'''
from __future__ import print_function, unicode_literals
import sys, datetime
from OpenGL import GL as gl, GLU as glu, GLUT as glut
import http_control
from opengl import main
__version__ = '1.0'

if __name__ == '__main__':
	main()
