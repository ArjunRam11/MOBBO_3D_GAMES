import numpy as np
import pyqtgraph.opengl as gl
from PyQt5 import QtWidgets
import colorsys
import random

class BoardMeshPlotter:
    def __init__(self, view):
        self.view = view
        self.board_meshes = {}  # Stores mesh items
        self.board_edges = {}   # Stores edge line items
        self.board_colors = {}  # Stores assigned colors
        self.text_labels = []   # Stores text labels
        self.reference_board_id = None

    def get_unique_color(self, board_id, reference_board_id):
        """Assigns unique colors to each board and ensures the reference board is Robin Egg Blue."""
        if board_id == reference_board_id:
            return (0, 204, 204, 255)  # Dark Robin Egg Blue

        if board_id not in self.board_colors:
            while True:
                hue = random.random()
                saturation = 0.5  
                value = 0.8  
                rgb = colorsys.hsv_to_rgb(hue, saturation, value)  
                rgba = tuple(int(c * 255) for c in rgb) + (128,)  # Convert to RGBA
                
                # Ensure color is not too close to Robin Egg Blue
                if not (rgba[0] < 50 and rgba[1] > 150 and rgba[2] > 150):  
                    self.board_colors[board_id] = rgba
                    break

        return self.board_colors[board_id]

    def update_board_edges(self, points, board_id, reference_board_id):
        """Creates edges for a board and returns the edge item."""
        z_plane = 0.026  # Keep all boards on the same plane (Z = 0)

        points = np.array(points)
        points[:, 2] = z_plane  
        edges = np.array([
            [points[0], points[1]],
            [points[1], points[2]],
            [points[2], points[3]],
            [points[3], points[0]]
        ])

        color = (1, 0, 0, 0.8) if board_id == reference_board_id else (1, 1, 0, 0.8)

        edge_vertices = edges.reshape(-1, 3)
        edge_item = gl.GLLinePlotItem(pos=edge_vertices, color=color, width=7, mode='lines')
        return edge_item

    def update_board_mesh(self, points, board_id, reference_board_id):
        """Creates a board with thickness and color based on the board ID."""
        board_thickness = 0.03  # Board thickness (2 cm)
        z_plane = 0.026  # Keep all boards on the same plane (Z = 0)

        top_points = np.array(points)
        top_points[:, 2] = z_plane  

        bottom_points = top_points - np.array([0, 0, board_thickness])

        vertexes = np.vstack([top_points, bottom_points])
        faces = np.array([
            [0, 1, 2], [2, 3, 0],  # Top face
            [4, 5, 6], [6, 7, 4],  # Bottom face
            [0, 1, 5], [5, 4, 0],  # Side face 1
            [1, 2, 6], [6, 5, 1],  # Side face 2
            [2, 3, 7], [7, 6, 2],  # Side face 3
            [3, 0, 4], [4, 7, 3]   # Side face 4
        ])

        selected_color = self.get_unique_color(board_id, reference_board_id)
        rgba_color = tuple(c / 255.0 for c in selected_color)

        colors = np.tile([rgba_color[0], rgba_color[1], rgba_color[2], rgba_color[3]], (faces.shape[0], 1))

        meshdata = gl.MeshData(vertexes=vertexes, faces=faces, faceColors=colors)
        mesh_item = gl.GLMeshItem(meshdata=meshdata, smooth=False, computeNormals=False)
        mesh_item.setGLOptions('additive')
        mesh_item.setGLOptions('translucent')

        return mesh_item

    def clear_previous_boards(self):
        """Removes all previous board meshes, edges, and text labels from the view."""
        for board_id in list(self.board_meshes.keys()):
            self.view.removeItem(self.board_meshes[board_id])
            del self.board_meshes[board_id]
        
        for board_id in list(self.board_edges.keys()):
            self.view.removeItem(self.board_edges[board_id])
            del self.board_edges[board_id]
        
        self.clear_text_labels()

    def update_boards(self, board_data, reference_board_id):
        """Update board meshes, edges, and labels dynamically."""
        self.clear_previous_boards()  # Ensure old items are removed before updating

        self.reference_board_id = reference_board_id

        for board_id, corners in board_data.items():
            if not np.any(corners):
                continue  # Skip empty boards

            # # Create and add new mesh
            # mesh_item = self.update_board_mesh(corners, board_id, reference_board_id)
            # self.view.addItem(mesh_item)
            # self.board_meshes[board_id] = mesh_item

            # Create and add new edges
            edge_item = self.update_board_edges(corners, board_id, reference_board_id)
            self.view.addItem(edge_item)
            self.board_edges[board_id] = edge_item

        # Update reference board labels
        if reference_board_id in board_data:
            self.update_reference_board_labels(board_data[reference_board_id])

    def update_reference_board_labels(self, corners):
        """Displays 'R' at each corner of the reference board."""
        self.clear_text_labels()
        for corner in corners:
            text_item = gl.GLTextItem(text='R', pos=corner)  # 'R' for reference
            self.view.addItem(text_item)
            self.text_labels.append(text_item)

    def clear_text_labels(self):
        """Clears all text labels."""
        for label in self.text_labels:
            self.view.removeItem(label)
        self.text_labels.clear()

if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = gl.GLViewWidget()
    window.show()

    plotter = BoardMeshPlotter(window)

    board_points_3d = {
        11: np.array([[0, 0, 0], [2, 0, 0], [2, 1, 0], [0, 1, 0]]),  
        22: np.array([[3, 1, 0], [5, 1, 0], [5, 2, 0], [3, 2, 0]]),  
        44: np.array([[1, 2, 0], [3, 2, 0], [3, 3, 0], [1, 3, 0]]),  
        77: np.array([[4, 0, 0], [6, 0, 0], [6, 1.5, 0], [4, 1.5, 0]]),  
    }

    reference_board_id = 22  

    plotter.update_boards(board_points_3d, reference_board_id)

    app.exec_()
