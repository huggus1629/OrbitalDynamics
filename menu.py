from panda3d.core import NodePath


class MenuInstance:
	def __init__(self, menu_obj, init_open):
		self.menu_obj = menu_obj
		self.is_open = init_open

	def close(self):
		if isinstance(self.menu_obj, NodePath):
			self.menu_obj.destroy()
			self.menu_obj = None
		self.is_open = False
