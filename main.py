from math import pi, sin, cos

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import loadPrcFileData, WindowProperties, TextNode
from direct.showbase.ShowBase import ShowBase
from direct.task import Task

import platform

running_windows = False
w, h = 1280, 720
if platform.system() == "Windows":
	running_windows = True
	import ctypes

	user32 = ctypes.windll.user32
	user32.SetProcessDPIAware()
	w, h = int(user32.GetSystemMetrics(0) / 2), int(user32.GetSystemMetrics(1) / 2)
w_mid, h_mid = w // 2, h // 2

confVars = f"""
win-size {w} {h}
window-title Orbital Dynamics
show-frame-rate-meter 1
sync-video 1
"""

loadPrcFileData("", confVars)


class MyApp(ShowBase):
	def __init__(self):
		ShowBase.__init__(self)

		self.skybox = self.loader.loadModel('skybox/skybox.gltf')
		self.skybox.setScale(2000)
		self.skybox.reparentTo(self.render)

		# disable default camera control
		self.disableMouse()

		# sets confined mode and hides the cursor:
		props = WindowProperties()
		props.setCursorHidden(True)
		props.setMouseMode(WindowProperties.M_confined)
		self.win.requestProperties(props)

		self.mouse_centered = False
		self.win_focused = True

		self.accept("window-event", self.handle_window_event)  # detects focus change

		self.accept("w", self.update_camera_xyz, ['w', False])
		self.accept("a", self.update_camera_xyz, ['a', False])
		self.accept("s", self.update_camera_xyz, ['s', False])
		self.accept("d", self.update_camera_xyz, ['d', False])

		# TODO wasd controls
		# TODO movement speed modifier
		# TODO shift to boost
		# TODO quit on esc
		# TODO menu

		self.mouse_dx_text = self.genLabelText(f"Mouse dx = --", 1)
		self.mouse_dy_text = self.genLabelText(f"Mouse dy = --", 2)

		self.cam_hdg_text = self.genLabelText(f"Camera heading = --°", 4)
		self.cam_ptc_text = self.genLabelText(f"Camera pitch = --°", 5)

		self.taskMgr.add(self.update_camera_hpr, "CameraUpdater")

	# ================ END INIT ====================

	def update_camera_xyz(self, key, boost: bool):
		if key == 'w':  # forward
			pass
		elif key == 'a':  # left
			pass
		elif key == 's':  # backward
			pass
		elif key == 'd':  # right
			pass

	def genLabelText(self, text, i):
		"""Macro for nice onscreen text (code taken from official Panda3D sample programs)"""
		return OnscreenText(text=text, pos=(0.06, -.06 * (i + 0.5)), fg=(1, 1, 1, 1), parent=self.a2dTopLeft,
																						align=TextNode.ALeft, scale=.05)

	def handle_window_event(self, window):
		"""Handles when the window gains or loses focus"""
		if window.getProperties().getForeground():
			print("Window gained focus")
			self.win_focused = True
			self.mouse_centered = False  # center mouse pointer without moving camera
		else:
			print("Window lost focus")
			self.win_focused = False

		# Check if the window is closed
		if not window.getProperties().getOpen():
			print("Window closed. Exiting application...")
			self.userExit()

	def reset_mouse(self):
		"""Resets mouse pointer position to the middle of the window"""
		if not self.mouseWatcherNode.hasMouse():
			return
		self.win.movePointer(0, w_mid, h_mid)

	def update_camera_hpr(self, task):
		"""Updates camera heading/pitch according to mouse input"""
		# Check if the mouse is available
		if not self.mouseWatcherNode.hasMouse():
			return Task.cont

		if not self.mouse_centered:  # center mouse pointer without moving camera
			self.win.movePointer(0, w_mid, h_mid)
			self.mouse_centered = True
			return Task.cont

		mouse_dx = self.mouseWatcherNode.getMouseX()
		mouse_dy = self.mouseWatcherNode.getMouseY()

		self.mouse_dx_text.text = f"Mouse dx = {mouse_dx}"
		self.mouse_dy_text.text = f"Mouse dy = {mouse_dy}"

		sensitivity = 100  # adjust this value for sensitivity

		# get current heading, pitch, and roll
		hdg, ptc, rll = self.camera.getHpr()

		hdg -= mouse_dx * sensitivity  # horizontal mouse movement changes heading
		ptc += mouse_dy * sensitivity  # vertical mouse movement changes pitch

		ptc = max(-90, min(90, ptc))  # clamps pitch to +-90°

		self.camera.setHpr(hdg, ptc, rll)

		self.cam_hdg_text.text = f"Camera heading = {hdg}°"
		self.cam_ptc_text.text = f"Camera pitch = {ptc}°"

		self.reset_mouse()  # recenters mouse pointer

		return Task.cont


app = MyApp()
app.run()
