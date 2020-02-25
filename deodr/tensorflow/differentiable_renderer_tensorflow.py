import numpy as np
from .. import differentiable_renderer_cython
import tensorflow as tf
from ..differentiable_renderer import Scene3D, Camera


class CameraTensorflow(Camera):
    def __init__(self, extrinsic, intrinsic, resolution, dist=None):
        super().__init__(extrinsic, intrinsic, resolution, dist=dist, checks=False)

    def world_to_camera(self, points_3d):
        assert isinstance(points_3d, tf.Tensor)
        return tf.linalg.matmul(
            tf.concat(
                (points_3d, tf.ones((points_3d.shape[0], 1), dtype=points_3d.dtype)),
                axis=1,
            ),
            tf.constant(self.extrinsic.T),
        )

    def left_mul_intrinsic(self, projected):
        assert isinstance(projected, tf.Tensor)
        return tf.linalg.matmul(
            tf.concat(
                (projected, tf.ones((projected.shape[0], 1), dtype=projected.dtype)),
                axis=1,
            ),
            tf.constant(self.intrinsic[:2, :].T),
        )

    def column_stack(self, values):
        return tf.stack(values, axis=1)


def TensorflowDifferentiableRender2D(ij, colors, scene):
    @tf.custom_gradient
    def forward(
        ij, colors
    ):  # using inner function as we don't differentate w.r.t scene
        nb_color_chanels = colors.shape[1]
        image = np.empty((scene.height, scene.width, nb_color_chanels))
        z_buffer = np.empty((scene.height, scene.width))
        scene.ij = np.array(ij)  # should automatically detached according to
        # https://pytorch.org/docs/master/notes/extending.html
        scene.colors = np.array(colors)
        scene.depths = np.array(scene.depths)
        differentiable_renderer_cython.renderScene(scene, 1, image, z_buffer)

        def backward(image_b):
            scene.uv_b = np.zeros(scene.uv.shape)
            scene.ij_b = np.zeros(scene.ij.shape)
            scene.shade_b = np.zeros(scene.shade.shape)
            scene.colors_b = np.zeros(scene.colors.shape)
            scene.texture_b = np.zeros(scene.texture.shape)
            image_copy = (
                image.copy()
            )  # making a copy to avoid removing antializaing on the image returned by
            # the forward pass (the c++ backpropagation undo antializating), could be
            # optional if we don't care about getting aliased images
            differentiable_renderer_cython.renderSceneB(
                scene, 1, image_copy, z_buffer, image_b.numpy()
            )
            return tf.constant(scene.ij_b), tf.constant(scene.colors_b)

        return tf.convert_to_tensor(image), backward

    return forward(ij, colors)


class Scene3DTensorflow(Scene3D):
    def __init__(self):
        super().__init__()

    def set_light(self, ligth_directional, ambiant_light):
        if not (isinstance(ligth_directional, tf.Tensor)):
            ligth_directional = tf.constant(ligth_directional)
        self.ligth_directional = ligth_directional
        self.ambiant_light = ambiant_light

    def _compute_vertices_colors_with_illumination(self):
        vertices_luminosity = (
            tf.nn.relu(
                -tf.reduce_sum(
                    self.mesh.vertex_normals * self.ligth_directional, axis=1
                )
            )
            + self.ambiant_light
        )
        return self.mesh.vertices_colors * vertices_luminosity[:, None]

    def _render_2d(self, ij, colors):

        return TensorflowDifferentiableRender2D(ij, colors, self), self.depths
