from direct.showbase.ShowBase import ShowBase
from panda3d.ai import Flock
from panda3d.core import NodePath, WindowProperties

# from main import MyApp


class MenuInstance:
	def __init__(self, menu_obj, init_open, *args):
		self.menu_obj = menu_obj
		self.is_open = init_open
		print(args)
		self.extraArgs = False
		if args:
			self.extraArgs = True
			self.base = args[0]
			self.props = args[1]

	def reg_open(self):
		self.is_open = True
		self.props.setCursorHidden(False)
		self.base.win.requestProperties(self.props)
		self.base.taskMgr.remove("CameraHprUpdater")

	def close(self):
		if isinstance(self.menu_obj, NodePath):
			self.menu_obj.destroy()
			self.menu_obj = None
		self.is_open = False

		if self.extraArgs:
			self.props.setCursorHidden(True)
			self.base.win.requestProperties(self.props)
			self.base.taskMgr.add(self.base.update_camera_hpr, "CameraHprUpdater")
