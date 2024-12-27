import math

from direct.showbase.Loader import Loader
from panda3d.core import NodePath, ModelNode, LineSegs

from tools import *


class CelBody:
	def __init__(self, base, name, model_path, init_pos, radius, mass, vec3_velocity: tuple[float, ...], color):
		self.node = NodePath(ModelNode(name))  # creates a ModelNode and wraps it in a NodePath
		self.name = name

		self.base = base
		self.loader = Loader(self.base)

		# load the planet model and attach it to the NodePath
		self.model = self.loader.loadModel(model_path)
		self.model.reparentTo(self.node)

		self.init_pos = init_pos
		self.node.setPos(self.init_pos)
		self.radius = radius
		self.node.setScale(self.radius)

		self.color = color
		self.node.setColor(self.color)

		self.trail = MotionTrail(self, self.color, -1)

		# given physical properties
		self.mass = mass
		self.vec3_velocity = list(vec3_velocity)

		self.l_vec3_f_forces = []
		self.vec3_f_fres = 0
		self.vec3_f_accel = 0

	# returns distance (center to center) to other celbody
	def distance(self, celbody):
		x1, y1, z1 = self.node.getPos()
		x2, y2, z2 = celbody.node.getPos()
		return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)

	def distance_m(self, celbody):
		return u_to_m(self.distance(celbody))

	# returns vector (in units) from self to celbody
	def vec3u_r(self, celbody):
		x1, y1, z1 = self.node.getPos()
		x2, y2, z2 = celbody.node.getPos()
		return tuple((x2 - x1, y2 - y1, z2 - z1))

	# returns vector (in meters) from self to celbody
	def vec3m_r(self, celbody):
		return vec_mul(self.vec3u_r(celbody), 10**8)


class MotionTrail:  # TODO optimizations
	def __init__(self, parent_celbody: CelBody, color, max_len):
		self.parent = parent_celbody
		self.trail_pts = [parent_celbody.init_pos]
		self.trail_color = color
		self.trail_max_len = max_len  # set to -1 for unlimited

		self.trail_obj = LineSegs()
		self.trail_obj.setColor(self.trail_color)

	def update_motion_trail(self):
		if len(self.trail_pts) == self.trail_max_len:  # if max len reached -> remove oldest point
			self.trail_pts.pop(0)

		pos = self.parent.node.getPos()
		last_pos = self.trail_pts[-1]

		# don't draw line if too close to previous point
		if vec_mag(vec_sum([pos, vec_neg(last_pos)])) < 1:
			return

		self.trail_pts.append(pos)  # add current position to motion trail

		self.trail_obj.moveTo(self.trail_pts[0])
		for p in self.trail_pts[1:]:
			self.trail_obj.drawTo(p)

		self.parent.base.render.attachNewNode(self.trail_obj.create(True))
