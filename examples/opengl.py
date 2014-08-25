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
__version__ = '1.0'

name = 'http_control demo'
width, height = (800, 600)
cam_x = 0.0
cam_y = 0.0
cam_z = -4.0
http_server = http_control.Server()

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

def lights():
	gl.glEnable(gl.GL_LIGHTING)
	lightZeroPosition = (0.0, 4.0, 4.0, 1.0)
	lightZeroColor = (1.0, 1.0, 1.0, 1.0)
	gl.glLightfv(gl.GL_LIGHT0, gl.GL_POSITION, lightZeroPosition)
	gl.glLightfv(gl.GL_LIGHT0, gl.GL_DIFFUSE, lightZeroColor)
	gl.glLightf(gl.GL_LIGHT0, gl.GL_CONSTANT_ATTENUATION, 0.5)
	gl.glLightf(gl.GL_LIGHT0, gl.GL_LINEAR_ATTENUATION, 0.05)
	gl.glEnable(gl.GL_LIGHT0)
	lightOnePosition = (0.0, -4.0, 0.0, 1.0)
	lightOneColor = (1.0, 1.0, 1.0, 1.0)
	gl.glLightfv(gl.GL_LIGHT1, gl.GL_POSITION, lightOnePosition)
	gl.glLightfv(gl.GL_LIGHT1, gl.GL_DIFFUSE, lightOneColor)
	gl.glLightf(gl.GL_LIGHT1, gl.GL_CONSTANT_ATTENUATION, 0.5)
	gl.glLightf(gl.GL_LIGHT1, gl.GL_LINEAR_ATTENUATION, 0.05)
	gl.glEnable(gl.GL_LIGHT1)

def camera():
	gl.glMatrixMode(gl.GL_PROJECTION)
	gl.glLoadIdentity()
	fov_y = 55.0
	aspect = float(width / height)
	near = 1.0
	far = 50.0
	glu.gluPerspective(fov_y, aspect, near, far)

def sphere():
	gl.glMatrixMode(gl.GL_MODELVIEW)
	gl.glLoadIdentity()
	gl.glColor(1.0, 1.0, 1.0, 1.0)
	glut.glutSolidSphere(1, 40, 40)

def display():
	update_from_http_control()
	gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
	camera()
	gl.glTranslate(cam_x, cam_y, cam_z)
	sphere()
	glut.glutSwapBuffers()

def update_from_http_control():
	global cam_x
	global cam_y
	global cam_z
	if http_server.updated():
		cam_x = http_server.get('cam_x')
		cam_y = http_server.get('cam_y')
		cam_z = http_server.get('cam_z')

def keyboard(key, x, y):
	global cam_x
	global cam_z
	
	if key == 'q' or key == '\033': # q or esc key
		http_server.stop()
		sys.exit(0)
	elif key == 'w':
		cam_z += 0.1
	elif key == 's':
		cam_z -= 0.1
	elif key == 'a':
		cam_x += 0.1
	elif key == 'd':
		cam_x -= 0.1
		
	glut.glutPostRedisplay()

if __name__ == '__main__':
	main()
