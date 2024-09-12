from direct.showbase.Loader import Loader
from direct.showbase.ShowBase import ShowBase
from panda3d.core import NodePath, ModelNode


class CelBody:
	def __init__(self, name, model_path):
		self.node = NodePath(ModelNode(name))  # creates a ModelNode and wraps it in a NodePath
		self.name = name

		self.loader = Loader()

		# load the planet model and attach it to the NodePath
		self.model = self.loader.loadModel(model_path)
		self.model.reparentTo(self.node)