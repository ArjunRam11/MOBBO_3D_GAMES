
import pyqtgraph.opengl as gl
import numpy as np

class CreateShape:
    def __init__(self,selected_color,view):
        super().__init__()
        self.selected_colors =  selected_color
        self.view=view
        self.mesh_items = {}  # Stores dynamically created mesh items

    # def create_cone(self, mesh_item, keypoints, radius, height, segments, color_key="cop"):

    def create_cone(self, mesh_item, keypoints, radius, height, segments, scoop_radius=0, phi_segments=0, theta_segments=0, color_key='cop'):
      
        """Creates and sets a cone mesh for visualization."""
        if keypoints is None or len(keypoints) == 0 or radius <= 0 or height <= 0 or segments <= 0:
            # Invisible placeholder for missing CoPs
            vertices = np.array([[0, 0, 0], [0, 0, 0], [0, 0, 0]])
            faces = np.array([[0, 1, 2]])
            invisible_color = (0, 0, 0, 0)
            colors = np.tile([invisible_color], (len(faces), 1))
            meshdata = gl.MeshData(vertexes=vertices, faces=faces, faceColors=colors)
            mesh_item.setMeshData(meshdata=meshdata, smooth=False, computeNormals=False)
            return
        

        
        cop_array = np.array(keypoints).flatten()  # Convert to a flat 1D array
         
        z=0.026      #the z value of cop
        x, y, z = cop_array  # Extract CoP coordinates
        
        apex = np.array([x, y, z + height])  # Cone apex



        apex = np.array([x, y, z + height])
        base_points = [
            [x + radius * np.cos(2 * np.pi * i / segments), 
                y + radius * np.sin(2 * np.pi * i / segments), 
                z - 0.06] 
            for i in range(segments)
        ]
        cone_vertices = np.array([apex] + base_points)
        cone_faces = [[0, (i + 1) % segments + 1, i + 1] for i in range(segments)]
        scoop_vertices = []
        scoop_faces = []
        if phi_segments > 0 and theta_segments > 0:
            for phi in range(phi_segments + 1):
                for theta in range(theta_segments):
                    angle_phi = np.pi * phi / phi_segments
                    angle_theta = 2 * np.pi * theta / theta_segments
                    sx = x + scoop_radius * np.sin(angle_phi) * np.cos(angle_theta)
                    sy = y + scoop_radius * np.sin(angle_phi) * np.sin(angle_theta)
                    sz = apex[2] + scoop_radius * np.cos(angle_phi)  # Center sphere at cone apex
                    scoop_vertices.append([sx, sy, sz])
            for phi in range(phi_segments):
                for theta in range(theta_segments):
                    current = phi * theta_segments + theta
                    next_theta = (theta + 1) % theta_segments
                    next_phi = (phi + 1) * theta_segments + theta
                    next_phi_theta = (phi + 1) * theta_segments + next_theta
                    if phi != phi_segments - 1:
                        scoop_faces.append([current, next_phi, next_phi_theta])
                    if phi != 0:
                        scoop_faces.append([current, next_phi_theta, next_theta + phi * theta_segments])
        if scoop_vertices:
            vertices = np.vstack((cone_vertices, np.array(scoop_vertices)))
            faces = np.vstack((cone_faces, np.array(scoop_faces) + len(cone_vertices)))
        else:
            vertices = cone_vertices
            faces = np.array(cone_faces)
        selected_color = self.selected_colors.get(color_key,self.selected_colors[color_key])
        rgba_color = tuple(c / 255.0 for c in selected_color)
        colors = np.tile([rgba_color], (len(faces), 1))
        meshdata = gl.MeshData(vertexes=np.array(vertices), faces=np.array(faces), faceColors=colors)
        mesh_item.setMeshData(meshdata=meshdata, smooth=False, computeNormals=False)
        mesh_item.setGLOptions('additive')
        mesh_item.setGLOptions('translucent')


    

    def create_circle_mesh(self, mesh_item, keypoints, radius, segments=36, color_key='cop'):
        """Creates and sets a circular mesh at z = 0.026."""


        if keypoints is None or len(keypoints) == 0 or radius <= 0 or segments <= 0:
            # Invisible placeholder for missing CoPs
            vertices = np.array([[0, 0, 0], [0, 0, 0], [0, 0, 0]])
            faces = np.array([[0, 1, 2]])
            invisible_color = (0, 0, 0, 0)
            colors = np.tile([invisible_color], (len(faces), 1))
            meshdata = gl.MeshData(vertexes=vertices, faces=faces, faceColors=colors)
            mesh_item.setMeshData(meshdata=meshdata, smooth=False, computeNormals=False)
            return
        

      
        # def create_circle_mesh(self, mesh_item, cop, radius=0.01, segments=36, color_key='cop'):
            """Creates and sets a 2D circular mesh at z = 0.026."""

        # Ensure `cop` is a 1D array and extract x, y
        cop_array = np.array(keypoints).flatten()  
        if len(cop_array) < 2:
            raise ValueError("Invalid CoP data: expected at least two values for (x, y).")
        if color_key =='cop':
            x, y = cop_array[:2]  # Get x, y
            z = 0.026  # Fix z-value
        else:
            x, y = cop_array[:2]  # Get x, y
            z = 0.024  # Fix z-value


        # Generate circle vertices
        circle_vertices = np.array([
            [x + radius * np.cos(2 * np.pi * i / segments), 
            y + radius * np.sin(2 * np.pi * i / segments), 
            z]
            for i in range(segments)
        ])

        # Center vertex
        center_vertex = np.array([[x, y, z]])  
        vertices = np.vstack((center_vertex, circle_vertices))

        # Faces: Triangles from center to circle edge
        faces = np.array([
            [0, i, (i + 1) % segments or 1]  
            for i in range(1, segments)
        ])

        # Get color
        selected_color = self.selected_colors.get(color_key, self.selected_colors[color_key])
        rgba_color = tuple(c / 255.0 for c in selected_color)
        colors = np.tile([rgba_color], (len(faces), 1))

        # Create mesh
        meshdata = gl.MeshData(vertexes=vertices, faces=faces, faceColors=colors)
        mesh_item.setMeshData(meshdata=meshdata, smooth=False, computeNormals=False)
        mesh_item.setGLOptions('translucent')  # Make it translucent
            

    def update_cop(self, mesh, cop, weight, is_gcop=False):
        """General function to update CoP visualization."""
        color_key = "gcop" if is_gcop else "cop"  # Use red for GCoP, green for CoPs
        if cop is not None and weight > 4:
            self.create_circle_mesh(mesh,cop,radius=0.025,segments=36 ,color_key=color_key)
            # self.create_cone(mesh, cop, radius=0.001, height=0.003, segments=20,scoop_radius=0.03, phi_segments=10, theta_segments=20, color_key=color_key)
        else:
            self.create_circle_mesh(mesh,cop,radius=0,segments=0 ,color_key=color_key)
            # self.create_cone(mesh, cop, radius=0, height=0, segments=0, scoop_radius=0.03, phi_segments=10, theta_segments=20,color_key=color_key)

    
    def update_all_cops(self, all_cops):
        """Update one mesh per board. Always renders all boards; hides stale slots."""
        n = len(all_cops)

        # Update / create a mesh for each current board
        for i, (cop, weight) in enumerate(all_cops):
            if i not in self.mesh_items:
                self.mesh_items[i] = gl.GLMeshItem()
                self.view.addItem(self.mesh_items[i])
            self.create_circle_mesh(self.mesh_items[i], cop.flatten(),
                                    radius=0.025, segments=36, color_key='cop')

        # Hide any mesh slots that no longer have a board
        for i in list(self.mesh_items.keys()):
            if i >= n:
                self.create_circle_mesh(self.mesh_items[i], np.array([0, 0, 0]),
                                        radius=0, segments=0, color_key='cop')
    
    

    def gcop_update(self, mesh, gcop1, weight):
        if gcop1 is not None:
            self.create_circle_mesh(mesh, gcop1, radius=0.02, segments=36, color_key='gcop')
        else:
            self.create_circle_mesh(mesh, gcop1, radius=0, segments=0, color_key='gcop')