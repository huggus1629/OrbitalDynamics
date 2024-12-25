from math import pi, sin, cos

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import loadPrcFileData, WindowProperties, TextNode, KeyboardButton, ClockObject
from direct.showbase.ShowBase import ShowBase
from direct.task import Task

import platform
import itertools as it
from scipy import constants
import datetime
import json

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

		# get the target frame rate directly from the graphics pipe
		display_info = self.pipe.getDisplayInformation()
		self.framerate = display_info.getDisplayModeRefreshRate(display_info.getCurrentDisplayModeIndex())

		kb = KeyboardButton()

		self.camLens.setFov(90)  # passing only horizontal fov automatically calculates vertical fov
		self.camLens.set_far(330000)  # enough to look across skybox
		self.camLens.set_near(0.1)

		self.camera.setPos(1495, 0, 0)

		# set up skybox
		self.skybox = self.loader.loadModel('skybox/skybox.gltf')
		self.skybox.setScale(94607)
		self.skybox.setShaderOff()
		self.skybox.setDepthWrite(False)
		self.skybox.setLightOff()
		self.skybox.reparentTo(self.render)

		self.axis = self.loader.loadModel('models/zup-axis')
		self.axis.setScale(1)
		self.axis.reparentTo(self.render)

		# ----------------- celestial bodies conf -----------------
		self.celbodies = []  # save all celestial bodies in this list

		# parse celestial bodies from json
		with open("config.json", "r") as config:
			# read json file as text and parse it into list/dict
			self.raw_celbodies = json.loads(config.read())

		for cb in self.raw_celbodies:
			# some shortcuts
			ip = cb['init_pos_m']
			r = cb['radius_m']
			m = cb['mass_kg']
			iv = cb['vec3_init_velocity']
			c_rgb = cb['rgb_color']
			# map values from 0-255 to float between 0 and 1 (required by panda3d)
			c_rgba = (c_rgb['r'] / 255, c_rgb['g'] / 255, c_rgb['b'] / 255, 1)

			self.celbodies.append(CelBody(self,
										cb['name'],
										cb['model_path'],
										(m_to_u(ip['x']), m_to_u(ip['y']), m_to_u(ip['z'])),
										m_to_u(r['mantissa'] * 10 ** r['exponent']),
										m['mantissa'] * 10 ** m['exponent'],
										(iv['x'], iv['y'], iv['z']),
										c_rgba))

		for cb in self.celbodies:
			# render all nodes
			cb.node.reparentTo(self.render)

		# TODO check for duplicate names (-> error)

		self.celbody_pairs = list(it.combinations(self.celbodies, 2))  # save all possible pairs in a list
		# ----------------- end celestial bodies conf -----------------

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
		self.accept("escape", self.userExit)  # quit on esc

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
		self.cam_spd_increment = 0.1
		self.cam_base_spd = round(float(1), digits_after_decimal(self.cam_spd_increment))

		self.accept("arrow_up", self.camera_change_speed, [True])
		self.accept("arrow_up-repeat", self.camera_change_speed, [True])
		self.accept("arrow_down", self.camera_change_speed, [False])
		self.accept("arrow_down-repeat", self.camera_change_speed, [False])

		self.accept("p", self.toggle_sim_state)  # toggle simulation pause state on p keypress

		self.vClock = ClockObject(ClockObject.M_non_real_time)  # create virtual timer by which the simulation runs
		self.vClock_speed = 60*24*28  # time factor
		self.running = False  # opens simulation in paused state
		self.clock.reset()
		self.vClock.reset()

		# some debug text
		self.realtime_elapsed_text = self.genLabelText(f"Realtime elapsed = -- s", 1)
		self.vtime_elapsed_text = self.genLabelText(f"Virtual time elapsed = ", 2)

		self.sim_running_text = self.genLabelText("", 4)
		self.update_sim_text(self.running)

		self.cam_pos_text = self.genLabelText(f"Cam xyz = (--, --, --)", 6)
		self.cam_spd_text = self.genLabelText(f"Cam speed = -- units/frame", 7)

		self.helptext = self.genLabelText(
			"""Move forwards - [W]
Move backwards - [S]
Move left - [A]
Move right - [D]
Move up - [Space]
Move down - [LCtrl]
Speed boost - [LShift]

Increase cam speed - [ArrowUp]
Decrease cam speed - [ArrowDown]

Play/Pause Simulation - [P]

Quit - [Esc]""",
			9)

		# ----- TASKS -----		(run every frame)
		self.taskMgr.add(self.update_camera_hpr, "CameraHprUpdater")
		self.taskMgr.add(self.update_camera_xyz, "CameraPosUpdater")
		self.taskMgr.add(self.update_vclock, "VirtualClockUpdater")
		self.taskMgr.add(self.update_time_counter, "TimeCounterUpdater")

		self.taskMgr.add(self.calc_forces, "ForceUpdater")

	# ================ END INIT ===================
	def toggle_sim_state(self):
		self.running = not self.running  # flip state
		self.update_sim_text(self.running)

	def update_sim_text(self, running):
		if running:  # if running
			self.sim_running_text.text = f"Simulation running @ {self.vClock_speed}x speed"
		else:  # if paused
			self.sim_running_text.text = f"Simulation paused (continue @ {self.vClock_speed}x speed)"

	def update_vclock(self, task):
		if self.running:
			self.vClock.setFrameRate(self.framerate / self.vClock_speed)
			self.vClock.tick()
		return task.cont

	def calc_forces(self, task):
		if not self.running:
			return task.cont

		dt = self.vClock.dt

		# for each pair of celbodies, calculate force vector
		for pair in self.celbody_pairs:
			# newton's gravitational law (F = G*m1*m2/r^2 * ř)
			magnitude = constants.G * pair[0].mass * pair[1].mass / (pair[0].distance_m(pair[1]) ** 3)
			vec3_r = pair[0].vec3m_r(pair[1])
			vec3_force = vec_mul(vec3_r, magnitude)

			# append calculated vector to vector list
			pair[0].l_vec3_f_forces.append(vec3_force)
			pair[1].l_vec3_f_forces.append(vec_neg(vec3_force))

		for celbody in self.celbodies:
			celbody.vec3_f_fres = vec_sum(celbody.l_vec3_f_forces)  # sum up all forces exerted on the body
			celbody.l_vec3_f_forces.clear()  # clear list of individual forces, making it ready for the next frame

			# using F = ma -> a = F/m calculate acceleration
			celbody.vec3_f_accel = vec_mul(celbody.vec3_f_fres, 1 / celbody.mass)

			# using v = a * dt calculate velocity change and new velocity
			vec3_f_dv = vec_mul(celbody.vec3_f_accel, dt)
			celbody.vec3_velocity = vec_sum([celbody.vec3_velocity, vec3_f_dv])  # add dv to previous v

			# using s = v * dt calculate displacement
			vec3_f_disp = vec_mul(celbody.vec3_velocity, dt)
			x, y, z = celbody.node.getPos()  # get xyz coords

			# add xyz components of displacement vector to corresponding variable
			x += m_to_u(vec3_f_disp[0])  #
			y += m_to_u(vec3_f_disp[1])  # convert from meters to panda3d units (personal definition: 1 u = 10^8 m)
			z += m_to_u(vec3_f_disp[2])  #

			# set the newly calculated position
			celbody.node.setPos(x, y, z)
			celbody.trail.update_motion_trail()

		return task.cont

	def update_time_counter(self, task):
		self.realtime_elapsed_text.text = f"Realtime elapsed = {round(self.clock.getFrameTime(), 3)} s"
		self.vtime_elapsed_text.text = f"Virtual time elapsed = {datetime.timedelta(seconds=self.vClock.getFrameTime())}"

		return task.cont

	def camera_change_speed(self, inc):
		"""
		Changes the camera's movement speed

		:param inc: ``True`` when increasing, ``False`` when decreasing speed
		"""
		inc = 1 if inc else -1  # convert boolean argument to pos/neg factor
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
							align=TextNode.ALeft, scale=.05)

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

		self.reset_mouse()  # recenters mouse pointer

		return task.cont


app = MyApp()
app.run()
