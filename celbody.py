from direct.showbase.Loader import Loader
from direct.showbase.ShowBase import ShowBase
from panda3d.core import NodePath, ModelNode

import math


class CelBody:
	def __init__(self, base, name, model_path, mass, vec3_velocity: tuple[float, ...]):
		self.node = NodePath(ModelNode(name))  # creates a ModelNode and wraps it in a NodePath
		self.name = name

		self.loader = Loader(base)

		# load the planet model and attach it to the NodePath
		self.model = self.loader.loadModel(model_path)
		self.model.reparentTo(self.node)

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
		return math.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)

	# returns vector from self to celbody
	def vec3_r(self, celbody):
		x1, y1, z1 = self.node.getPos()
		x2, y2, z2 = celbody.node.getPos()
		return tuple((x2 - x1, y2 - y1, z2 - z1))
