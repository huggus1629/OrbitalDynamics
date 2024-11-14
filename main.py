from math import pi, sin, cos

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import loadPrcFileData, WindowProperties, TextNode, KeyboardButton
from direct.showbase.ShowBase import ShowBase
from direct.task import Task

import platform
import itertools as it
from scipy import constants

from celbody import CelBody
from tools import *

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

		self.camLens.setFov(90)  # passing only horizontal fov automatically calculates vertical fov
		self.camLens.set_far(330000)  # enough to look across skybox

		# set up skybox
		self.skybox = self.loader.loadModel('skybox/skybox.gltf')
		self.skybox.setScale(94607)
		self.skybox.setShaderOff()
		self.skybox.setDepthWrite(False)
		self.skybox.setLightOff()
		self.skybox.reparentTo(self.render)

		self.axis = self.loader.loadModel('models/zup-axis')
		self.axis.setScale(10)
		self.axis.reparentTo(self.render)

		# ----------------- celestial bodies conf -----------------
		self.celbodies = []

		self.testearth = CelBody(self, "planet", "./custom_models/sphere.gltf", 6 * 10**24, (0, 0, 0))
		self.testearth.node.setScale(60)
		self.testearth.node.reparentTo(self.render)
		self.celbodies.append(self.testearth)

		self.testmoon = CelBody(self, "moon", "./custom_models/sphere.gltf", 7 * 10**22, (0, 0, 0))
		self.testmoon.node.setScale(20)
		self.testmoon.node.setPos(100, 0, 0)
		self.testmoon.node.reparentTo(self.render)
		self.celbodies.append(self.testmoon)

		self.celbody_pairs = list(it.combinations(self.celbodies, 2))
		# ----------------- end celestial bodies conf -----------------
		# print(self.celbodies[0].distance(self.celbodies[1]))

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
		self.accept("escape", self.userExit)

		# "The name of this class is a bit misleading -
		# it listens for keyboard events as well."
		self.isDown = self.mouseWatcherNode.isButtonDown
		# ----- button definitions -----
		self.forward_btn = kb.asciiKey('w')
		self.left_btn = kb.asciiKey('a')
		self.backward_btn = kb.asciiKey('s')
		self.right_btn = kb.asciiKey('d')

		self.up_btn = kb.space()
		self.down_btn = kb.lcontrol()

		self.boost_btn = kb.lshift()
		# ----- end button definitions -----

		# camera speed
		self.cam_spd_increment = 10
		self.cam_base_spd = round(float(1), digits_after_decimal(self.cam_spd_increment))

		self.accept("arrow_up", self.camera_change_speed, [True])
		self.accept("arrow_up-repeat", self.camera_change_speed, [True])
		self.accept("arrow_down", self.camera_change_speed, [False])
		self.accept("arrow_down-repeat", self.camera_change_speed, [False])

		# TODO menu

		# some debug text
		self.realtime_elapsed_text = self.genLabelText(f"Realtime elapsed = -- s", 1)
		self.cam_pos_text = self.genLabelText(f"Cam xyz = (--, --, --)", 3)
		self.cam_hdg_text = self.genLabelText(f"Cam heading = --°", 5)
		self.cam_ptc_text = self.genLabelText(f"Cam pitch = --°", 6)
		self.cam_spd_text = self.genLabelText(f"Cam speed = -- units/frame", 7)
		self.cam_fov_text = self.genLabelText(f"Cam FOV = {self.camLens.getFov()[0]}", 9)

		# ----- TASKS -----		(run every frame)
		self.taskMgr.add(self.update_camera_hpr, "CameraHprUpdater")
		self.taskMgr.add(self.update_camera_xyz, "CameraPosUpdater")
		self.taskMgr.add(self.update_time_counter, "TimeCounterUpdater")

		self.taskMgr.add(self.calc_forces, "ForceUpdater")

	# ================ END INIT ===================
	def calc_forces(self, task):
		dt = self.clock.dt

		# for each pair of celbodies, calculate force
		for pair in self.celbody_pairs:
			magnitude = constants.G * pair[0].mass * pair[1].mass / (pair[0].distance(pair[1]) ** 3)
			vec3_r = pair[0].vec3_r(pair[1])
			vec3_force = vec_mul(vec3_r, magnitude)
			# print(f"({magnitude} = {constants.G} * {pair[0].mass} * {pair[1].mass} / ({pair[0].distance(pair[1])} ** 2))")
			pair[0].l_vec3_f_forces.append(vec3_force)
			pair[1].l_vec3_f_forces.append(vec_neg(vec3_force))

		for celbody in self.celbodies:
			celbody.vec3_f_fres = vec_sum(celbody.l_vec3_f_forces)
			celbody.l_vec3_f_forces.clear()  # clear individual forces after calculating fres

			# using F = ma -> a = F/m calculate acceleration
			celbody.vec3_f_accel = vec_mul(celbody.vec3_f_fres, 1/celbody.mass)

			# using v = a * dt calculate velocity change and new velocity
			vec3_dv = vec_mul(celbody.vec3_f_accel, dt)
			celbody.vec3_velocity = vec_sum([celbody.vec3_velocity, vec3_dv])
			print(dt)
			print(f"{celbody.name}:\n\tFres = {celbody.vec3_f_fres}\n\ta = {celbody.vec3_f_accel}\n\tv = {celbody.vec3_velocity}")

			# using s = v * dt calculate displacement
			vec3_disp = vec_mul(celbody.vec3_velocity, dt)
			x, y, z = celbody.node.getPos()
			x += vec3_disp[0] * 10**-8  #
			y += vec3_disp[1] * 10**-8  # convert from meters to panda3d units
			z += vec3_disp[2] * 10**-8  #
			celbody.node.setPos(x, y, z)

		return task.cont

	def update_time_counter(self, task):
		self.realtime_elapsed_text.text = f"Realtime elapsed = {round(self.clock.getRealTime(), 3)} s"

		return task.cont

	def camera_change_speed(self, inc):
		"""
		Changes the camera's movement speed

		:param inc: ``True`` when increasing, ``False`` when decreasing speed
		"""
		inc = 1 if inc else -1  # convert bool to factor
		self.cam_base_spd += inc * self.cam_spd_increment
		# cam speed can't go below min increment
		rnd_digits = digits_after_decimal(self.cam_spd_increment)
		self.cam_base_spd = round(max(0 + self.cam_spd_increment, self.cam_base_spd), rnd_digits)

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

		movement_speed = self.cam_base_spd * self.camera_speed_mod(2)
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

		return task.cont

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

		return task.cont


app = MyApp()
app.run()
