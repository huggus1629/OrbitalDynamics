from math import pi, sin, cos
import platform

running_windows = False
w, h = 1280, 720
if platform.system() == "Windows":
	running_windows = True
	import ctypes

	user32 = ctypes.windll.user32
	user32.SetProcessDPIAware()
	w, h = int(user32.GetSystemMetrics(0) / 2), int(user32.GetSystemMetrics(1) / 2)

from panda3d.core import loadPrcFileData, WindowProperties

confVars = f"""
win-size {w} {h}
window-title Orbital Dynamics
show-frame-rate-meter 1
sync-video 1
"""

loadPrcFileData("", confVars)

from direct.showbase.ShowBase import ShowBase
from direct.task import Task


class MyApp(ShowBase):
	def __init__(self):
		ShowBase.__init__(self)

		self.skybox = self.loader.loadModel('skybox/skybox.gltf')
		self.skybox.setScale(2000)
		self.skybox.reparentTo(self.render)

		# Disable default camera control
		self.disableMouse()

		# To set confined mode and hide the cursor:
		props = WindowProperties()
		props.setCursorHidden(True)
		props.setMouseMode(WindowProperties.M_confined)
		self.win.requestProperties(props)
		# self.taskMgr.doMethodLater(0, self.resolveMouse, "Resolve mouse setting")

		# TODO center mouse ptr
		# TODO wasd
		# TODO quit on esc
		# TODO menu

		self.prev_mouse_x = 0
		self.prev_mouse_y = 0

		self.taskMgr.add(self.update_camera, "CameraUpdater")

	# def resolveMouse(self, task):
	# 	props = self.win.getProperties()
	#
	# 	actualMode = props.getMouseMode()
	# 	if actualMode != WindowProperties.M_relative:
	# 		print("Could not set relative mouse mode! :(")

	def update_camera(self, task):
		# Check if the mouse is available
		if self.mouseWatcherNode.hasMouse():
			mouse_x = self.mouseWatcherNode.getMouseX()
			mouse_y = self.mouseWatcherNode.getMouseY()

			delta_x = mouse_x - self.prev_mouse_x
			delta_y = mouse_y - self.prev_mouse_y

			# Store the current position for the next frame
			self.prev_mouse_x = mouse_x
			self.prev_mouse_y = mouse_y

			sensitivity = 100  # Adjust this value for sensitivity

			# Get the current heading, pitch, and roll
			hdg, ptc, rll = self.camera.getHpr()

			hdg -= delta_x * sensitivity  # Horizontal mouse movement rotates yaw (heading)
			ptc += delta_y * sensitivity  # Vertical mouse movement rotates pitch

			self.camera.setHpr(hdg, ptc, rll)

		return Task.cont


app = MyApp()
app.run()
