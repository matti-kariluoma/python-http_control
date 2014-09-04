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
from opengl import (init, main, display)
__version__ = '1.0'

def display_then_poll():
	display()
	glut.glutPostRedisplay()

if __name__ == '__main__':
	init()
	glut.glutDisplayFunc(display_then_poll)
	main()
