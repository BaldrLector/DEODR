from DEODR.obj import readObj
from DEODR.triangulated_mesh import ColoredTriMesh
from DEODR import differentiable_renderer
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import trimesh
import cv2
import time
from scipy.spatial.transform import Rotation
import os


class Interactor:
    def __init__(self, camera, mode="object_centered_trackball", object_center=None):
        self.left_is_down = False
        self.right_is_down = False
        self.mode = mode
        self.object_center = object_center
        self.rotation_speed = 0.003
        self.translation_speed = 0.05
        self.camera = camera

    def mouseCallback(self, event, x, y, flags, param):

        if event == cv2.EVENT_LBUTTONDOWN:
            self.left_is_down = True
            self.x_last = x
            self.y_last = y
        # check to see if the left mouse button was released
        if event == cv2.EVENT_LBUTTONUP:
            self.left_is_down = False
        if event == cv2.EVENT_RBUTTONDOWN:
            self.right_is_down = True
            self.x_last = x
            self.y_last = y
            # check to see if the left mouse button was released
        if event == cv2.EVENT_RBUTTONUP:
            self.right_is_down = False
        if self.left_is_down:
            if self.mode == "camera_centered":
                Rot = Rotation.from_rotvec(
                    np.array(
                        [
                            -self.rotation_speed * (y - self.y_last),
                            self.rotation_speed * (x - self.x_last),
                            0,
                        ]
                    )
                )
                self.camera.extrinsic = Rot.as_dcm().dot(self.camera.extrinsic)
                self.x_last = x
                self.y_last = y
            if self.mode == "object_centered_trackball":

                Rot = Rotation.from_rotvec(
                    np.array(
                        [
                            self.rotation_speed * (y - self.y_last),
                            -self.rotation_speed * (x - self.x_last),
                            0,
                        ]
                    )
                )
                nR = Rot.as_dcm().dot(self.camera.extrinsic[:, :3])
                nt = (
                    self.camera.extrinsic[:, :3].dot(self.object_center)
                    + self.camera.extrinsic[:, 3]
                    - nR.dot(self.object_center)
                )
                self.camera.extrinsic = np.column_stack((nR, nt))
                self.x_last = x
                self.y_last = y
            else:
                raise (baseException(f"unkown camera mode {self.mode}"))

        if self.right_is_down:
            if self.mode == "camera_centered":
                self.camera.extrinsic[2, 3] += self.translation_speed * (
                    self.y_last - y
                )
                self.x_last = x
                self.y_last = y
            if self.mode == "object_centered_trackball":
                self.camera.extrinsic[2, 3] += self.translation_speed * (
                    self.y_last - y
                )
                self.x_last = x
                self.y_last = y
            else:
                raise (baseException(f"unkown camera mode {self.mode}"))


def mesh_viewer(
    obj_file, display_texture_map=True, SizeW=640, SizeH=480, display_fps=True
):
    mesh_trimesh = trimesh.load(obj_file)
    mesh = ColoredTriMesh.from_trimesh(mesh_trimesh)
    if display_texture_map:
        ax = plt.subplot(111)
        if mesh.textured:
            mesh.plot_uv_map(ax)

    objectCenter = 0.5 * (mesh.vertices.max(axis=0) + mesh.vertices.min(axis=0))
    objectRadius = np.max(mesh.vertices.max(axis=0) - mesh.vertices.min(axis=0))

    cameraCenter = objectCenter + np.array([0, 0, 3]) * objectRadius
    focal = 2 * SizeW

    R = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])
    T = -R.T.dot(cameraCenter)
    extrinsic = np.column_stack((R, T))
    intrinsic = np.array([[focal, 0, SizeW / 2], [0, focal, SizeH / 2], [0, 0, 1]])

    dist = [0, 0, 0, 0, 0]
    camera = differentiable_renderer.Camera(
        extrinsic=extrinsic, intrinsic=intrinsic, resolution=(SizeW, SizeH), dist=dist
    )

    handColor = np.array([200, 100, 100]) / 255
    mesh.setVerticesColors(np.tile(handColor, [mesh.nbV, 1]))

    scene = differentiable_renderer.Scene3D()
    scene.setLight(ligthDirectional=np.array([-0.5, 0, -0.5]), ambiantLight=0.3)
    scene.setMesh(mesh)
    backgroundImage = np.ones((SizeH, SizeW, 3))
    scene.setBackground(backgroundImage)

    mesh.texture = mesh.texture[
        :, :, ::-1
    ]  # convert texture to GBR to avoid future conversion when ploting in Opencv

    fps = 0
    fps_decay = 0.1
    windowname = f"DEODR mesh viewer:{obj_file}"

    interactor = Interactor(camera=camera, object_center=objectCenter)

    cv2.namedWindow(windowname)
    cv2.setMouseCallback(windowname, interactor.mouseCallback)

    while cv2.getWindowProperty(windowname, 0) >= 0:
        # mesh.setVertices(mesh.vertices+np.random.randn(*mesh.vertices.shape)*0.001)
        start = time.clock()
        Abuffer = scene.render(interactor.camera)

        if display_fps:
            font = cv2.FONT_HERSHEY_SIMPLEX
            bottomLeftCornerOfText = (20, SizeH - 20)
            fontScale = 1
            fontColor = (0, 0, 255)
            thickness = 2
            cv2.putText(
                Abuffer,
                "fps:%0.1f" % fps,
                bottomLeftCornerOfText,
                font,
                fontScale,
                fontColor,
                thickness,
            )

        cv2.imshow(windowname, Abuffer)
        stop = time.clock()
        fps = (1 - fps_decay) * fps + fps_decay * (1 / (stop - start))
        key = cv2.waitKey(1)


def example():
    obj_file = os.path.join(os.path.dirname(__file__), "models/duck.obj")
    mesh_viewer(obj_file)


if __name__ == "__main__":
    example()
