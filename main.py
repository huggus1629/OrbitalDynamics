from math import pi, sin, cos

from panda3d.core import loadPrcFileData

confVars = """
win-size 1280 720
window-title Orbital Dynamics
show-frame-rate-meter 1
show-scene-graph-analyzer-meter 1
sync-video 1
"""

loadPrcFileData("", confVars)

from direct.showbase.ShowBase import ShowBase
from direct.task import Task


class MyApp(ShowBase):
	def __init__(self):
		ShowBase.__init__(self)

		#self.skybox_texture = self.loader.loadCubeMap('skybox/cubemap_#.png')
		self.skybox = self.loader.loadModel('skybox/skybox.gltf')
		self.skybox.setScale(2000)
		self.skybox.reparentTo(self.render)
		#self.skybox.setTexture(self.skybox_texture, 1)
		# self.taskMgr.add(self.spinCameraTask, "SpinCameraTask") (NOT USED, EXAMPLE ONLY)

	# Define a procedure to move the camera. (NOT USED, EXAMPLE ONLY)
	def spinCameraTask(self, task):
		angleDegrees = task.time * 24.0
		angleRadians = angleDegrees * (pi / 180.0)
		self.camera.setPos(20 * sin(angleRadians), -20 * cos(angleRadians), 3)
		self.camera.setHpr(angleDegrees, 0, 0)
		return Task.cont


app = MyApp()
app.run()
