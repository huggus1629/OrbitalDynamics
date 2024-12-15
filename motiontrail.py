from panda3d.core import LRGBColor

from celbody import CelBody


class MotionTrail:
	def __init__(self, parent_celbody: CelBody, init_pos):
		self.parent = parent_celbody
		self.motiontrail_pts = [init_pos]
		self.motiontrail_color = LRGBColor(255, 0, 0)

	def update_motion_trail(self):
		self.motiontrail_pts.append(self.parent.node.getPos())
