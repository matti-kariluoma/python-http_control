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
from opengl import (width, height, name, lights, display, keyboard, 
		http_server, cam_x, cam_y, cam_z)
__version__ = '1.0'

def main():
	glut.glutInit(sys.argv)
	glut.glutInitDisplayMode(glut.GLUT_DOUBLE | glut.GLUT_RGB | glut.GLUT_DEPTH)
	glut.glutInitWindowSize(width, height)
	glut.glutCreateWindow(name)
	black = (0.0, 0.0, 0.0, 1.0)
	gl.glClearColor(*black)
	gl.glShadeModel(gl.GL_SMOOTH)
	gl.glEnable(gl.GL_CULL_FACE)
	gl.glEnable(gl.GL_DEPTH_TEST)
	lights()
	glut.glutDisplayFunc(display)
	glut.glutKeyboardFunc(keyboard)
	http_server.register('cam_x', cam_x)
	http_server.register('cam_y', cam_y)
	http_server.register('cam_z', cam_z)
	http_server.start()
	glut.glutMainLoop()
	return

if __name__ == '__main__':
	main()
