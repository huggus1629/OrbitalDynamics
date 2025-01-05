import datetime
import itertools as it
import json
import math
import platform
import sys
from math import pi, sin, cos

from direct.gui.DirectEntry import DirectEntry
from direct.gui.DirectLabel import DirectLabel
from direct.gui.DirectOptionMenu import DirectOptionMenu
from direct.gui.OnscreenText import OnscreenText
from direct.interval.IntervalManager import ivalMgr
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import loadPrcFileData, WindowProperties, TextNode, KeyboardButton, ClockObject, NodePath
from scipy import constants

from celbody import CelBody
from menu import MenuInstance
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

		self.camera: NodePath = self.camera

		# get the target frame rate directly from the graphics pipe
		display_info = self.pipe.getDisplayInformation()
		self.framerate = display_info.getDisplayModeRefreshRate(display_info.getCurrentDisplayModeIndex())

		kb = KeyboardButton()

		self.camLens.setFov(90)  # passing only horizontal fov automatically calculates vertical fov
		self.camLens.set_far(330000)  # enough to look across skybox
		self.camLens.set_near(0.05)

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

		seen = set()
		duplicates = set()  # store duplicates to notify user of duplicate entries

		for i, cb in enumerate(self.raw_celbodies):
			if cb['name'] in seen:
				duplicates.add((cb['name'], i))
				continue

			seen.add(cb['name'])

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

		if duplicates:
			print(f"There {'is' if len(duplicates) == 1 else 'are'} {len(duplicates)} "
				f"duplicate {'entry' if len(duplicates) == 1 else 'entries'}:")
			for d in sorted(list(duplicates), key=lambda x: x[1]):
				print(f"\t-\t'{d[0]}' @ JSON pos. {d[1]}")
			print("\nThey will not be added to the simulation\n")

		for cb in self.celbodies:
			# render all nodes
			cb.node.reparentTo(self.render)

		self.celbody_pairs = list(it.combinations(self.celbodies, 2))  # save all possible pairs in a list
		# ----------------- end celestial bodies conf -----------------

		# disable default camera control
		self.disableMouse()

		# sets confined mode and hides the cursor:
		self.props = WindowProperties()
		self.props.setCursorHidden(True)
		self.props.setMouseMode(WindowProperties.M_confined)
		self.win.requestProperties(self.props)

		# some flags used for preserving camera orientation
		self.mouse_centered = False
		self.win_focused = True

		self.accept("window-event", self.handle_window_event)  # detects focus change

		self.open_menus = []  # stores MenuInstances of any open dialogs/menus
		self.accept("escape", self.esc_handler)  # handles escape press

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

		self.accept("t", self.enter_sim_speed)  # show sim speed text entry box
		self.accept("c", self.enter_cam_speed)  # show cam speed text entry box

		self.accept("f", self.pause_then_exec, [self.trk_selection])

		self.vClock = ClockObject(ClockObject.M_non_real_time)  # create virtual timer by which the simulation runs
		self.vClock_speed = float(60*24*28)  # time factor
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

		self.helptext_tip = self.genLabelText(f"Hold [H] to show controls", 9)

		self.helptext_obj = None
		self.helptext = \
"""\
Look around - [Mouse]
Move forwards - [W]
Move backwards - [S]
Move left - [A]
Move right - [D]
Move up - [Space]
Move down - [LCtrl]
Speed boost - [LShift]

Increase cam speed - [ArrowUp]
Decrease cam speed - [ArrowDown]
Enter custom cam speed - [C]

Play/pause simulation - [P]
Adjust simulation speed - [T]

Follow object - [F]
Insert new object - [I] (WIP)

Close menu / Quit - [Esc]"""

		self.accept("h", self.toggle_helptext, [True])
		self.accept("h-up", self.toggle_helptext, [False])

		# init empty MenuInstances
		self.sim_speed_entry = MenuInstance(None, False)
		self.cam_speed_entry = MenuInstance(None, False)

		self.tracking_selection = MenuInstance(None, False, self, WindowProperties())
		self.tracking = False
		self.trk_min_distance = None
		self.trk_init_distance = None
		self.trk_h = 0
		self.trk_p = 0
		self.accept("wheel_up", self.distance_update_trk_mode, [False])
		self.accept("wheel_down", self.distance_update_trk_mode, [True])
		self.tracking_tooltip = self.genLabelText(5 * '\t' + "Press [Esc] to leave tracking mode\n" +
												5 * '\t' + "Press [P] to continue", 2)
		self.tracking_tooltip.hide()

		# ----- TASKS -----		(run every frame)
		self.taskMgr.add(self.update_camera_hpr, "CameraHprUpdater")
		self.taskMgr.add(self.update_camera_xyz, "CameraPosUpdater")
		self.taskMgr.add(self.update_vclock, "VirtualClockUpdater")
		self.taskMgr.add(self.update_time_counter, "TimeCounterUpdater")

		self.taskMgr.add(self.calc_forces, "ForceUpdater")

		self.taskMgr.add(self.update_nametags, "NameTagUpdater")

	# ================ END INIT ===================

	def cleanup_tracking(self, leave):
		self.tracking_tooltip.hide()
		txt: str = self.tracking_tooltip.text
		if '\n' not in txt:
			txt += '\n' + 5 * '\t' + "Press [P] to continue"
			self.tracking_tooltip.text = txt
		self.taskMgr.remove("TrackingCameraUpdater")
		self.taskMgr.add(self.update_camera_hpr, "CameraHprUpdater")
		self.taskMgr.add(self.update_camera_xyz, "CameraPosUpdater")
		self.taskMgr.add(self.update_nametags, "NameTagUpdater")
		self.tracking = not leave
		self.props.setCursorHidden(True)
		self.win.requestProperties(self.props)

	def init_tracking(self, cb_name):
		if self.running:
			self.toggle_sim_state()

		self.tracking = True
		print(f"requested {cb_name} tracking")
		# self.tracking_selection.menu_obj.hide()
		self.esc_handler()

		txt: str = self.tracking_tooltip.text
		if '\n' not in txt:
			txt += '\n' + 5 * '\t' + "Press [P] to continue"
			self.tracking_tooltip.text = txt
		self.tracking_tooltip.show()

		cb = None

		for loop_cb in self.celbodies:
			if loop_cb.name == cb_name:
				cb = loop_cb
				break

		self.trk_init_distance = 5
		self.trk_min_distance = cb.radius

		print(f"radius: {cb.radius}\ninit: {self.trk_init_distance}\nmin: {self.trk_min_distance}\n")

		cb_pos = cb.node.getPos()

		self.camera.setPos(cb_pos[0] + max(self.trk_init_distance, self.trk_min_distance), cb_pos[1], cb_pos[2])
		self.camera.lookAt(cb.node)

		# self.camera.reparentTo(cb.node)

		self.props.setCursorHidden(True)
		self.win.requestProperties(self.props)

		self.taskMgr.remove("CameraHprUpdater")
		self.taskMgr.remove("CameraPosUpdater")
		self.taskMgr.remove("NameTagUpdater")
		self.taskMgr.add(self.cam_update_trk_mode, "TrackingCameraUpdater", extraArgs=[Task, cb])

	def distance_update_trk_mode(self, inc):
		inc = 1 if inc else -1
		sensitivity = 0.1
		self.trk_init_distance += sensitivity * inc
		self.trk_init_distance = max(self.trk_min_distance, self.trk_init_distance)

	def cam_update_trk_mode(self, task, cb: CelBody):
		txt: str = self.tracking_tooltip.text
		if self.running and '\n' in txt:
			self.tracking_tooltip.text = txt.split('\n')[0]

		if not self.mouseWatcherNode.hasMouse():
			return task.cont

		# Mouse delta from the center
		mouse_x = self.mouseWatcherNode.getMouseX()
		mouse_y = self.mouseWatcherNode.getMouseY()

		self.reset_mouse()
		
		sensitivity = 1.5
		d = self.trk_init_distance * cb.radius

		# Apply the mouse deltas to rotate the pivot node
		delta_x = mouse_x * sensitivity
		delta_y = mouse_y * sensitivity

		self.trk_h -= delta_x  # Horizontal rotation
		self.trk_p -= delta_y  # Vertical rotation
		self.trk_p = max(-math.radians(85), min(math.radians(85), self.trk_p))
		x = cb.node.getX() + d * -cos(self.trk_h) * cos(self.trk_p)
		y = cb.node.getY() + d * -sin(self.trk_h) * cos(self.trk_p)
		z = cb.node.getZ() + d * sin(self.trk_p)

		self.camera.setPos(x, y, z)
		self.camera.lookAt(cb.node)

		self.update_nametags(Task)

		return task.cont

	def trk_selection(self, task):
		if self.open_menus:
			return task.done

		if not self.tracking_selection.menu_obj:
			self.tracking_selection.menu_obj = DirectOptionMenu(items=[cb.name for cb in self.celbodies],
																scale=0.075,
																command=self.init_tracking)
			trk_sel_label = DirectLabel(parent=self.tracking_selection.menu_obj,
										text='Select object to track',
										text_fg=(1, 1, 1, 1),
										text_bg=(0, 0, 0, 1),
										text_scale=1,
										text_pos=(-5.25, 0))

		self.tracking_selection.menu_obj.show()
		self.tracking_selection.reg_open()
		self.taskMgr.remove("CameraHprUpdater")
		self.taskMgr.remove("CameraPosUpdater")
		self.taskMgr.remove("TrackingCameraUpdater")
		self.open_menus.append(self.tracking_selection)
		return task.done

	def pause_then_exec(self, fn, *args):
		if self.running:
			self.toggle_sim_state()
			self.update_vclock(Task)
			self.update_sim_text(self.running)

		self.taskMgr.doMethodLater(0, fn, None, extraArgs=[Task, *args])
		# self.taskMgr.step()

	# scale and rotate name tags according to camera position
	def update_nametags(self, task):
		for cb in self.celbodies:
			x, y, z = cb.node.getPos()
			cb.nametag_np.setPos(x, y, z + 1.2 * cb.radius)  # place name tag slightly above CelBody

			x_nt, y_nt, z_nt = cb.nametag_np.getPos()
			x_cam, y_cam, z_cam = self.camera.getPos()
			# fancy math to get pitch and heading
			new_p = math.degrees(math.atan2(z_nt - z_cam, math.sqrt((x_cam - x_nt) ** 2 + (y_cam - y_nt) ** 2)))
			new_h = math.degrees(math.atan2(y_cam - y_nt, x_cam - x_nt)) + 90
			cb.nametag_np.setHpr(new_h, new_p, 0)

			# make name tag bigger the further away camera is
			d = math.sqrt((x_cam - x_nt) ** 2 + (y_cam - y_nt) ** 2 + (z_cam - z_nt) ** 2)
			cb.nametag_np.setScale(0.1 * d ** (1/1.1))

		return task.cont

	# shows controls as long as H is held down
	def toggle_helptext(self, show):
		if self.open_menus:
			return

		if show:
			self.helptext_obj = self.genLabelText(self.helptext, 11)
		else:
			self.helptext_obj.destroy()

	# sets camera speed to custom value
	def set_cam_speed(self, s_new_speed):
		try:
			new_speed = float(s_new_speed)
		except ValueError:
			print("Enter a valid number!", file=sys.stderr)
			self.esc_handler()
			self.enter_cam_speed()  # reopens in case of failed attempt
			return

		self.cam_base_spd = new_speed
		self.esc_handler()

	# brings up custom cam speed entry box
	def enter_cam_speed(self):
		if self.open_menus:
			# abort if it's already open
			return

		self.cam_speed_entry.menu_obj = DirectEntry(initialText=str(self.cam_base_spd),
													scale=0.05,
													numLines=1,
													focus=True,
													command=self.set_cam_speed)
		cam_speed_entry_label = DirectLabel(parent=self.cam_speed_entry.menu_obj,
											text='Enter desired camera movement speed:',
											text_fg=(1, 1, 1, 1),
											text_bg=(0, 0, 0, 1),
											text_pos=(0, 2))

		self.cam_speed_entry.is_open = True
		self.open_menus.append(self.cam_speed_entry)

	# sets simulation speed to custom value
	def set_sim_speed(self, s_new_speed):
		try:
			new_speed = float(s_new_speed)
		except ValueError:
			print("Enter a valid number!", file=sys.stderr)
			self.esc_handler()
			self.enter_sim_speed()  # reopens in case of failed attempt
			return

		self.vClock_speed = new_speed
		self.update_vclock(Task)
		self.update_sim_text(self.running)
		self.esc_handler()

	# brings up custom simulation speed entry box
	def enter_sim_speed(self):
		if self.open_menus:
			# abort if it's already open
			return

		self.sim_speed_entry.menu_obj = DirectEntry(initialText=str(self.vClock_speed),
													scale=0.05,
													numLines=1,
													focus=True,
													command=self.set_sim_speed)
		sim_speed_entry_label = DirectLabel(parent=self.sim_speed_entry.menu_obj,
											text='Enter desired simulation speed:',
											text_fg=(1, 1, 1, 1),
											text_bg=(0, 0, 0, 1),
											text_pos=(0, 2))

		self.sim_speed_entry.is_open = True
		self.open_menus.append(self.sim_speed_entry)

	def toggle_sim_state(self):
		if self.open_menus:
			# if a MenuInstance is open, ignore p keypress
			return

		self.running = not self.running  # flip state
		self.update_sim_text(self.running)

	def update_sim_text(self, running):
		if running:  # if running
			self.sim_running_text.text = f"Simulation running @ {self.vClock_speed}x speed"
		else:  # if paused
			self.sim_running_text.text = f"Simulation paused (continue @ {self.vClock_speed}x speed)"

	def update_vclock(self, task):
		self.vClock.setFrameRate(self.framerate / self.vClock_speed)  # sets the time factor
		if self.running:
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
		if self.open_menus:
			# ignore movement if there are open MenuInstances
			return task.cont

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

	# closes MenuInstance if applicable, otherwise quits app
	def esc_handler(self):
		if self.open_menus:
			if self.open_menus[-1] == self.tracking_selection:
				self.open_menus.pop()
				self.tracking_selection.menu_obj.hide()
				self.cleanup_tracking(False)
				return
			self.open_menus.pop().close()
		elif self.tracking:
			self.cleanup_tracking(True)
			self.open_menus.clear()
		else:
			self.userExit()


app = MyApp()
app.run()
