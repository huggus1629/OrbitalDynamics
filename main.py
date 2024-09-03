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

		# Load the environment model.
		self.scene = self.loader.loadModel("models/environment")

		# Reparent the model to render.
		self.scene.reparentTo(self.render)

		# Apply scale and position transforms on the model.
		self.scene.setScale(0.25, 0.25, 0.25)
		self.scene.setPos(-8, 42, 0)
		# Add the spinCameraTask procedure to the task manager.

		self.taskMgr.add(self.spinCameraTask, "SpinCameraTask")

	# Define a procedure to move the camera.

	def spinCameraTask(self, task):
		angleDegrees = task.time * 6.0
		angleRadians = angleDegrees * (pi / 180.0)
		self.camera.setPos(20 * sin(angleRadians), -20 * cos(angleRadians), 3)
		self.camera.setHpr(angleDegrees, 20 * sin(5 * angleRadians), 0)
		return Task.cont


app = MyApp()
app.run()
