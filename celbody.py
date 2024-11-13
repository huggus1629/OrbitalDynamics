from direct.showbase.Loader import Loader
from direct.showbase.ShowBase import ShowBase
from panda3d.core import NodePath, ModelNode


class CelBody:
	def __init__(self, base, name, model_path, mass, vec3_velocity):
		self.node = NodePath(ModelNode(name))  # creates a ModelNode and wraps it in a NodePath
		self.name = name

		self.loader = Loader(base)

		# load the planet model and attach it to the NodePath
		self.model = self.loader.loadModel(model_path)
		self.model.reparentTo(self.node)

		# given physical properties
		self.mass = mass
		self.vec3_velocity = vec3_velocity

		self.frame_force = 0