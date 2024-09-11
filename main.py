from math import pi, sin, cos

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import loadPrcFileData, WindowProperties, TextNode, KeyboardButton
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
		kb = KeyboardButton()

		# set up skybox
		self.skybox = self.loader.loadModel('skybox/skybox.gltf')
		self.skybox.setScale(30000)
		self.skybox.setShaderOff()
		self.skybox.setDepthWrite(False)
		self.skybox.setLightOff()
		self.skybox.reparentTo(self.render)

		# test box
		self.testmodel = self.loader.loadModel('models/box')
		self.testmodel.setScale(10)
		self.testmodel.reparentTo(self.render)

		# disable default camera control
		self.disableMouse()

		# sets confined mode and hides the cursor:
		props = WindowProperties()
		props.setCursorHidden(True)
		props.setMouseMode(WindowProperties.M_confined)
		self.win.requestProperties(props)

		# some flags used for preserving camera orientation
		self.mouse_centered = False
		self.win_focused = True

		self.accept("window-event", self.handle_window_event)  # detects focus change

		self.isDown = self.mouseWatcherNode.isButtonDown	# "The name of this class is a bit misleading -
															# it listens for keyboard events as well."
		# ----- button definitions -----
		self.forward_btn = kb.asciiKey('w')
		self.left_btn = kb.asciiKey('a')
		self.backward_btn = kb.asciiKey('s')
		self.right_btn = kb.asciiKey('d')

		self.up_btn = kb.space()
		self.down_btn = kb.lcontrol()

		self.boost_btn = kb.lshift()
		# ----- end button definitions -----

		# TODO fix misaligned edge on skybox (UV unwrap in blender)
		# TODO quit on esc
		# TODO menu

		# some debug text
		self.cam_pos_text = self.genLabelText(f"Cam xyz = (--, --, --)", 1)
		self.cam_hdg_text = self.genLabelText(f"Cam heading = --°", 3)
		self.cam_ptc_text = self.genLabelText(f"Cam pitch = --°", 4)
		self.cam_spd_text = self.genLabelText(f"Cam speed = -- units/frame", 5)

		# ----- TASKS -----		(run every frame)
		self.taskMgr.add(self.update_camera_hpr, "CameraHprUpdater")
		self.taskMgr.add(self.update_camera_xyz, "CameraPosUpdater")

	# ================ END INIT ====================

	def camera_speed_mod(self, multiplier):
		"""Returns the specified multiplier only when boost button is held down, returns 1 otherwise"""

		if self.isDown(self.boost_btn):
			return multiplier
		else:
			return 1

	def update_camera_xyz(self, task):
		"""Task for updating the camera's XYZ coordinates according to keyboard input (WASD by default)"""

		cam_x, cam_y, cam_z = self.camera.getPos()
		self.cam_pos_text.text = f"Cam xyz = ({cam_x:.3f}, {cam_y:.3f}, {cam_z:.3f})"

		movement_speed = 1 * self.camera_speed_mod(1.5)
		self.cam_spd_text.text = f"Cam speed = {movement_speed} units/frame"

		cam_h, cam_p, cam_r = self.camera.getHpr()
		cam_h *= pi / 180  # conversion to radians
		cam_p *= pi / 180

		if self.isDown(self.forward_btn):
			cam_x -= cos(cam_p) * sin(cam_h) * movement_speed
			cam_y += cos(cam_p) * cos(cam_h) * movement_speed
			cam_z += sin(cam_p) * movement_speed
		if self.isDown(self.left_btn):
			cam_x -= cos(cam_h) * movement_speed
			cam_y -= sin(cam_h) * movement_speed
		if self.isDown(self.backward_btn):
			cam_x += cos(cam_p) * sin(cam_h) * movement_speed
			cam_y -= cos(cam_p) * cos(cam_h) * movement_speed
			cam_z -= sin(cam_p) * movement_speed
		if self.isDown(self.right_btn):
			cam_x += cos(cam_h) * movement_speed
			cam_y += sin(cam_h) * movement_speed
		if self.isDown(self.up_btn):
			cam_z += movement_speed
		if self.isDown(self.down_btn):
			cam_z -= movement_speed

		self.camera.setPos(cam_x, cam_y, cam_z)  # moves camera to newly calculated position

		return Task.cont

	def genLabelText(self, text, i):
		"""Macro for nice onscreen text (code taken from official Panda3D sample programs)"""

		return OnscreenText(text=text, pos=(0.06, -.06 * (i + 0.5)), fg=(1, 1, 1, 1), parent=self.a2dTopLeft,
																						align=TextNode.ALeft, scale=.04)

	def handle_window_event(self, window):
		"""Handles when the window gains or loses focus"""

		if window.getProperties().getForeground():
			print("Window gained focus")
			self.win_focused = True
			self.mouse_centered = False  # this flag tells the CameraHprUpdater to preserve mouse orientation
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
		"""Task for updating the camera's heading/pitch according to mouse input"""

		# Check if the mouse is available
		if not self.mouseWatcherNode.hasMouse():
			return Task.cont

		if not self.mouse_centered:  # center mouse pointer without moving camera
			self.win.movePointer(0, w_mid, h_mid)
			self.mouse_centered = True
			return Task.cont

		mouse_dx = self.mouseWatcherNode.getMouseX()
		mouse_dy = self.mouseWatcherNode.getMouseY()

		sensitivity = 100  # adjust this value for sensitivity

		# get current heading, pitch, and roll
		hdg, ptc, rll = self.camera.getHpr()

		hdg -= mouse_dx * sensitivity  # horizontal mouse movement changes heading
		ptc += mouse_dy * sensitivity  # vertical mouse movement changes pitch

		ptc = max(-90, min(90, ptc))  # clamps pitch to +-90°

		self.camera.setHpr(hdg, ptc, rll)

		self.cam_hdg_text.text = f"Cam heading = {hdg:.3f}°"
		self.cam_ptc_text.text = f"Cam pitch = {ptc:.3f}°"

		self.reset_mouse()  # recenters mouse pointer

		return Task.cont


app = MyApp()
app.run()
