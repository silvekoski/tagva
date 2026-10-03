import json
import math
from dataclasses import dataclass, field

import bpy
import numpy as np
from mathutils import Vector

import textures

PAINTS = {
    "ral7035": (0.80, 0.81, 0.79), "white": (0.93, 0.93, 0.91), "ral7032": (0.73, 0.72, 0.64), "ral9002": (0.86, 0.85, 0.80),
    "beige": (0.82, 0.78, 0.68), "ral7038": (0.70, 0.72, 0.70), "midgrey": (0.55, 0.57, 0.57), "darkgrey": (0.33, 0.35, 0.36),
    "bluegrey": (0.45, 0.52, 0.58),
}
CABLE_COLORS = [(0.9, 0.9, 0.88), (0.85, 0.85, 0.85), (0.1, 0.1, 0.1), (0.55, 0.55, 0.55), (0.75, 0.7, 0.1), (0.15, 0.3, 0.7), (0.6, 0.2, 0.1)]
PLATE_TEX_WIDTH = 1024
KEY_HEIGHT = 0.0015
PORT_HEIGHT = 0.006
HOUSING_DEPTH = 0.03


def lin(c):
    return tuple(float(v) ** 2.2 for v in c)


def kelvin_rgb(k):
    t = k / 100.0
    r = 1.0 if t <= 66 else min(1.0, 1.292936 * (t - 60) ** -0.1332047)
    g = min(1.0, 0.39008 * math.log(t) - 0.631841) if t <= 66 else min(1.0, 1.129891 * (t - 60) ** -0.0755148)
    b = 1.0 if t >= 66 else (0.0 if t <= 19 else min(1.0, 0.543207 * math.log(t - 10) - 1.196254))
    return lin((r, g, b))


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def node_tree_material(name):
    mat = bpy.data.materials.new(name)
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    return mat, mat.node_tree.nodes, mat.node_tree.links


def principled(nodes):
    return next(n for n in nodes if n.type == "BSDF_PRINCIPLED")


def objcolor_material(name, metallic=0.0, bump=0.0, emission=False):
    """Base color from the object color, roughness from its alpha. Emission variant: strength = alpha * 40."""
    mat, nodes, links = node_tree_material(name)
    bsdf = principled(nodes)
    info = nodes.new("ShaderNodeObjectInfo")
    if emission:
        out = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
        em = nodes.new("ShaderNodeEmission")
        mul = nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = 40.0
        links.new(info.outputs["Color"], em.inputs["Color"])
        links.new(info.outputs["Alpha"], mul.inputs[0])
        links.new(mul.outputs[0], em.inputs["Strength"])
        links.new(em.outputs[0], out.inputs["Surface"])
        return mat
    links.new(info.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(info.outputs["Alpha"], bsdf.inputs["Roughness"])
    bsdf.inputs["Metallic"].default_value = metallic
    if bump > 0:
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 900.0
        bmp = nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = bump
        links.new(noise.outputs["Fac"], bmp.inputs["Height"])
        links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def image(name, w, h, alpha=False, linear=False):
    img = bpy.data.images.new(name, w, h, alpha=alpha, float_buffer=linear)
    img.colorspace_settings.name = "Linear Rec.709" if linear else "sRGB"
    return img


def texture_material(name, w, h, emission=False, alpha=False):
    """Principled material on an sRGB image. Emission from a second, linear float image times the strength input."""
    mat, nodes, links = node_tree_material(name)
    bsdf = principled(nodes)
    col = image(name + "-color", w, h, alpha)
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = col
    tex.interpolation = "Linear"
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha:
        links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.45
    em_img = None
    if emission:
        em_img = image(name + "-emit", w, h, linear=True)
        etex = nodes.new("ShaderNodeTexImage")
        etex.image = em_img
        links.new(etex.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 0.0
    return mat, col, em_img


def glass_material():
    mat, nodes, links = node_tree_material("glass")
    out = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
    for n in list(nodes):
        if n.type == "BSDF_PRINCIPLED":
            nodes.remove(n)
    glass = nodes.new("ShaderNodeBsdfGlass")
    glass.inputs["IOR"].default_value = 1.5
    glass.inputs["Roughness"].default_value = 0.0
    trans = nodes.new("ShaderNodeBsdfTransparent")
    path = nodes.new("ShaderNodeLightPath")
    mix = nodes.new("ShaderNodeMixShader")
    links.new(path.outputs["Is Shadow Ray"], mix.inputs[0])
    links.new(glass.outputs[0], mix.inputs[1])
    links.new(trans.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    return mat, glass


def mesh_object(name, verts, faces, uvs=None, mats=None, materials=()):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    if uvs is not None:
        uv = me.uv_layers.new(name="UVMap")
        loop_uv = [uvs[vi] for f in faces for vi in f]
        uv.data.foreach_set("uv", np.array(loop_uv, np.float32).ravel())
    for m in materials:
        me.materials.append(m)
    if mats is not None:
        me.polygons.foreach_set("material_index", np.array(mats, np.int32))
    me.update()
    return link(bpy.data.objects.new(name, me))


def box_geometry(x0, x1, y0, y1, z0, z1, sides="all"):
    """Box faces with outward normals. sides: subset of 'front back left right top bottom' (front = +y)."""
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = {"bottom": (0, 3, 2, 1), "top": (4, 5, 6, 7), "back": (0, 1, 5, 4), "front": (2, 3, 7, 6), "left": (3, 0, 4, 7), "right": (1, 2, 6, 5)}
    names = list(f) if sides == "all" else sides.split()
    return v, [f[n] for n in names], names


def unit_cube(name, materials, front_slot=0, other_slot=1, inward=False):
    """Unit cube centered at the origin; the front face (+y) gets UV 0..1 and front_slot, others other_slot."""
    v, faces, names = box_geometry(-0.5, 0.5, -0.5, 0.5, -0.5, 0.5)
    verts, fs, uvs, mats = [], [], [], []
    for face, n in zip(faces, names):
        base = len(verts)
        for k, vi in enumerate(face):
            verts.append(v[vi])
            x, y, z = v[vi]
            uvs.append((0.5 - x, z + 0.5) if n == "front" else (0.0, 0.0))
        fs.append(tuple(reversed(range(base, base + 4))) if inward else tuple(range(base, base + 4)))
        mats.append(front_slot if n == "front" else other_slot)
    return mesh_object(name, verts, fs, uvs, mats, materials)


def plate_mesh(name, w, h, regions, materials):
    """Front plate (material 0) at y = HOUSING_DEPTH with raised keys and port cover, housing sides (material 1) behind it."""
    verts, faces, uvs, mats = [], [], [], []

    def uv(x, z):
        return ((w / 2 - x) / w, (z + h / 2) / h)

    def add(v, f, mat):
        base = len(verts)
        verts.extend(v)
        uvs.extend(uv(x, z) for x, _, z in v)
        faces.extend(tuple(base + i for i in face) for face in f)
        mats.extend([mat] * len(f))

    add([(-w / 2, HOUSING_DEPTH, -h / 2), (w / 2, HOUSING_DEPTH, -h / 2), (w / 2, HOUSING_DEPTH, h / 2), (-w / 2, HOUSING_DEPTH, h / 2)],
        [(0, 3, 2, 1)], 0)
    raised = [(k["box"], KEY_HEIGHT) for k in regions["keys"]] + [(regions["port"], PORT_HEIGHT)]
    for (u0, v0, u1, v1), height in raised:
        x0, x1 = w / 2 - u1 * w, w / 2 - u0 * w
        z0, z1 = h / 2 - v1 * h, h / 2 - v0 * h
        v, f, _ = box_geometry(x0, x1, HOUSING_DEPTH - 0.0005, HOUSING_DEPTH + height, z0, z1, "front left right top bottom")
        add(v, f, 0)
    v, f, _ = box_geometry(-w / 2, w / 2, 0.0, HOUSING_DEPTH - 0.0002, -h / 2, h / 2, "left right top bottom")
    add(v, f, 1)
    return mesh_object(name, verts, faces, uvs, mats, materials)


@dataclass
class Plate:
    kind: str
    obj: object
    width: float
    height: float
    texture: object
    color_img: object
    emit_img: object
    material: object


@dataclass
class Textured:
    obj: object
    color_img: object
    emit_img: object = None
    material: object = None
    kind: str = ""


@dataclass
class Door:
    x0: float
    x1: float
    z0: float
    z1: float
    front: float
    lv: bool
    taken: list = field(default_factory=list)

    def free(self, x0, x1, z0, z1, pad=0.02):
        if x0 < self.x0 + 0.03 or x1 > self.x1 - 0.03 or z0 < self.z0 + 0.03 or z1 > self.z1 - 0.03:
            return False
        return all(x1 + pad <= a or x0 - pad >= b or z1 + pad <= c or z0 - pad >= d for a, b, c, d in self.taken)

    def place(self, rng, w, h, z_range=None, tries=30):
        for _ in range(tries):
            x = rng.uniform(self.x0 + w / 2 + 0.03, self.x1 - w / 2 - 0.03) if self.x1 - self.x0 > w + 0.06 else None
            lo, hi = z_range or (self.z0 + h / 2 + 0.03, self.z1 - h / 2 - 0.03)
            lo, hi = max(lo, self.z0 + h / 2 + 0.03), min(hi, self.z1 - h / 2 - 0.03)
            if x is None or hi <= lo:
                return None
            z = rng.uniform(lo, hi)
            if self.free(x - w / 2, x + w / 2, z - h / 2, z + h / 2):
                self.taken.append((x - w / 2, x + w / 2, z - h / 2, z + h / 2))
                return x, z
        return None


class SynthScene:
    def __init__(self, assets, profile):
        self.p = profile
        self.scene = bpy.context.scene
        for ob in list(bpy.data.objects):
            bpy.data.objects.remove(ob)
        self.glyphs = textures.Glyphs(self.load_gray(assets / "glyphs.png"), assets / "glyphs.json")
        self.objcolor = objcolor_material("objcolor")
        self.paint = objcolor_material("paint", bump=0.04)
        self.metal = objcolor_material("metal", metallic=0.8)
        self.emissive = objcolor_material("tube", emission=True)
        self.glass_mat, self.glass_bsdf = glass_material()
        self.plates = []
        for kind, count in (("rex615", 4), ("narrow615", 2)):
            regions = json.loads((assets / f"{kind}-regions.json").read_text())
            base = self.load_rgba(assets / f"{kind}-front.png")
            th = round(base.shape[0] * PLATE_TEX_WIDTH / base.shape[1])
            base = textures.resize(base, th, PLATE_TEX_WIDTH)
            tex = textures.PlateTexture(base, regions, self.glyphs)
            w, h = regions["plate_mm"][0] / 1000, regions["plate_mm"][1] / 1000
            for i in range(count):
                mat, col, em = texture_material(f"{kind}-{i}", PLATE_TEX_WIDTH, th, emission=True)
                obj = plate_mesh(f"{kind}-{i}", w, h, regions, [mat, self.objcolor])
                self.plates.append(Plate(kind, obj, w, h, tex, col, em, mat))
        self.devices = []
        for i in range(8):
            mat, col, em = texture_material(f"device-{i}", 384, 384, emission=True)
            self.devices.append(Textured(unit_cube(f"device-{i}", [mat, self.objcolor]), col, em, mat))
        self.labels = []
        for kind, count, size in (("nameplate", 5, (512, 128)), ("tape", 3, (512, 128)), ("sticker", 6, (128, 128))):
            for i in range(count):
                mat, col, _ = texture_material(f"{kind}-{i}", *size, alpha=kind == "sticker")
                self.labels.append(Textured(unit_cube(f"{kind}-{i}", [mat, self.objcolor]), col, None, mat, kind))
        self.vents = []
        mat, col, _ = texture_material("vent", 256, 256)
        col.pixels.foreach_set(textures.srgb_rgba(textures.vent(256, 256, 14)))
        for i in range(3):
            self.vents.append(unit_cube(f"vent-{i}", [mat, self.objcolor]))
        self.openings = []
        for i in range(2):
            mat, col, _ = texture_material(f"opening-{i}", 256, 256)
            self.openings.append(Textured(unit_cube(f"opening-{i}", [mat, self.objcolor]), col))
        self.panel_parts = [unit_cube(f"panel-{i}", [self.paint]) for i in range(30)]
        self.small = [unit_cube(f"small-{i}", [self.objcolor]) for i in range(10)]
        self.knobs = []
        for i in range(8):
            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.5, depth=1.0)
            ob = bpy.context.active_object
            ob.name = f"knob-{i}"
            ob.rotation_euler = (math.pi / 2, 0, 0)
            ob.data.materials.append(self.objcolor)
            self.knobs.append(ob)
        self.tray = self.make_tray()
        self.cables = []
        for i in range(8):
            cu = bpy.data.curves.new(f"cable-{i}", "CURVE")
            cu.dimensions = "3D"
            cu.bevel_resolution = 2
            sp = cu.splines.new("BEZIER")
            sp.bezier_points.add(4)
            ob = link(bpy.data.objects.new(f"cable-{i}", cu))
            ob.data.materials.append(self.objcolor)
            self.cables.append(ob)
        self.glass = unit_cube("glass", [self.glass_mat], 0, 0)
        self.glass_frame = [unit_cube(f"glass-frame-{i}", [self.paint]) for i in range(4)]
        self.room_mats = []
        for n in ("wall", "floor", "ceiling"):
            mat, nodes, _ = node_tree_material(n)
            self.room_mats.append(principled(nodes))
            principled(nodes).inputs["Roughness"].default_value = 0.8
        self.room = self.make_room()
        self.tubes = [unit_cube(f"tube-{i}", [self.emissive]) for i in range(6)]
        for t in self.tubes:
            t.visible_diffuse = t.visible_shadow = False
        self.lights = []
        for i in range(6):
            ld = bpy.data.lights.new(f"area-{i}", "AREA")
            ld.shape = "RECTANGLE"
            self.lights.append(link(bpy.data.objects.new(f"area-{i}", ld)))
        sd = bpy.data.lights.new("spot", "SPOT")
        self.spot = link(bpy.data.objects.new("spot", sd))
        pd = bpy.data.lights.new("point", "POINT")
        self.point = link(bpy.data.objects.new("point", pd))
        cam = bpy.data.cameras.new("camera")
        cam.lens_unit = "FOV"
        cam.sensor_fit = "HORIZONTAL"
        cam.clip_start = 0.03
        cam.clip_end = 60.0
        self.camera = link(bpy.data.objects.new("camera", cam))
        self.scene.camera = self.camera
        world = bpy.data.worlds.new("world")
        self.scene.world = world
        if hasattr(world, "use_nodes"):
            world.use_nodes = True
        self.world_bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
        self.transparent = {self.glass.name}
        self.all_dynamic = ([p.obj for p in self.plates] + [d.obj for d in self.devices] + [t.obj for t in self.labels] + self.vents
                            + [o.obj for o in self.openings] + self.panel_parts + self.small + self.knobs + [self.tray] + self.cables
                            + [self.glass] + self.glass_frame + self.tubes + self.lights + [self.spot, self.point])

    def load_pixels(self, path):
        img = bpy.data.images.load(str(path))
        w, h = img.size
        a = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(a)
        bpy.data.images.remove(img)
        return a.reshape(h, w, 4)[::-1]

    def load_rgba(self, path):
        a = self.load_pixels(path).copy()
        a[..., 3] = 1.0
        return a

    def load_gray(self, path):
        return np.ascontiguousarray(self.load_pixels(path)[..., 0])

    def make_tray(self):
        verts, faces = [], []
        parts = [(-0.5, 0.5, -0.15, -0.13, 0.0, 0.08), (-0.5, 0.5, 0.13, 0.15, 0.0, 0.08)]
        parts += [(x - 0.01, x + 0.01, -0.13, 0.13, 0.0, 0.02) for x in np.linspace(-0.48, 0.48, 9)]
        for p in parts:
            v, f, _ = box_geometry(*p)
            base = len(verts)
            verts += v
            faces += [tuple(base + i for i in face) for face in f]
        return mesh_object("tray", verts, faces, materials=[self.metal])

    def make_room(self):
        ob = unit_cube("room", [bpy.data.materials["wall"], bpy.data.materials["floor"], bpy.data.materials["ceiling"]], 0, 0, inward=True)
        me = ob.data
        idx = []
        for poly in me.polygons:
            n = poly.normal
            idx.append(1 if n.z > 0.5 else 2 if n.z < -0.5 else 0)
        me.polygons.foreach_set("material_index", np.array(idx, np.int32))
        return ob

    def set_box(self, ob, center, size, color=None, rough=0.5):
        ob.location = center
        ob.scale = size
        ob.rotation_euler = (0, 0, 0)
        if color is not None:
            ob.color = (*color, rough)
        ob.hide_render = False

    def push(self, img, rgba):
        if img.size[0] != rgba.shape[1] or img.size[1] != rgba.shape[0]:
            img.scale(rgba.shape[1], rgba.shape[0])
        img.pixels.foreach_set(textures.srgb_rgba(rgba))
        img.update()

    def randomize(self, rng, want_target):
        for ob in self.all_dynamic:
            ob.hide_render = True
        doors, panels_x = self.lineup(rng)
        placed = self.place_plates(rng, doors, want_target)
        self.place_distractors(rng, doors)
        top = max(d.z1 for d in doors) + 0.1
        target = self.pick_target(rng, placed, doors)
        cam_pos, fov = self.place_camera(rng, target)
        self.room_and_lights(rng, panels_x, top, cam_pos, target)
        self.occluders(rng, placed, doors, panels_x, top, cam_pos, target)
        self.finish_emission(rng)
        bpy.context.view_layer.update()
        return placed, target, fov

    def lineup(self, rng):
        p = self.p
        lineup = rng.random() < p["lineup_prob"]
        n = int(rng.integers(3, 8)) if lineup else int(rng.integers(1, 3))
        style = "switchgear" if rng.random() < p["switchgear_prob"] else "cabinet"
        names = list(PAINTS)
        paint = PAINTS[rng.choice(names, p=p["paint_weights"])]
        height = rng.uniform(1.9, 2.4)
        widths = rng.uniform(0.45, 0.9, n) if style == "switchgear" else rng.uniform(0.5, 1.2, n)
        x = -widths.sum() / 2
        doors, parts = [], iter(self.panel_parts)
        for w in widths:
            col = lin(np.clip(np.array(paint) * rng.uniform(0.97, 1.03), 0, 1))
            rough = rng.uniform(0.3, 0.7)
            depth = rng.uniform(0.0, 0.03) if rng.random() < 0.3 else 0.0
            self.set_box(next(parts), (x + w / 2, -0.4 + depth, height / 2), (w - 0.004, 0.8, height), lin(np.array(paint) * 0.8), rough)
            front = depth + rng.uniform(0.015, 0.03)
            if style == "switchgear":
                lv = rng.uniform(0.55, 0.85)
                z_split = height - lv - 0.03
                for z0, z1, is_lv in ((z_split + 0.006, height - 0.04, True), (0.12, z_split - 0.006, False)):
                    self.set_box(next(parts), (x + w / 2, depth + (front - depth) / 2, (z0 + z1) / 2), (w - 0.02, front - depth, z1 - z0), col, rough)
                    doors.append(Door(x + 0.01, x + w - 0.01, z0, z1, front, is_lv))
            else:
                z0, z1 = 0.12, height - 0.08
                self.set_box(next(parts), (x + w / 2, depth + (front - depth) / 2, (z0 + z1) / 2), (w - 0.02, front - depth, z1 - z0), col, rough)
                doors.append(Door(x + 0.01, x + w - 0.01, z0, z1, front, True))
            x += w
        return doors, (-widths.sum() / 2, widths.sum() / 2)

    def mount(self, ob, door, x, z, depth_scale=1.0, y_extra=0.0):
        ob.location = (x, door.front + y_extra, z)
        ob.rotation_euler = (0, 0, 0)
        ob.scale = (1, depth_scale, 1)
        ob.hide_render = False

    def place_plates(self, rng, doors, want_target):
        p = self.p
        placed = []
        rex = [pl for pl in self.plates if pl.kind == "rex615"]
        narrow = [pl for pl in self.plates if pl.kind == "narrow615"]
        lv_doors = [d for d in doors if d.lv] or doors
        n_rex = int(rng.choice(np.arange(1, 5), p=p["rex_count_weights"])) if want_target else 0
        n_narrow = int(rng.random() < p["narrow_prob"]) + int(rng.random() < p["narrow_prob"] * 0.3)
        kinds = ["rex615"] * min(n_rex, len(rex)) + ["narrow615"] * min(n_narrow, len(narrow))
        rng.shuffle(kinds)
        order = list(rng.permutation(len(lv_doors)))
        pools = {"rex615": iter(rex), "narrow615": iter(narrow)}
        k = 0
        for kind in kinds:
            pl = next(pools[kind])
            spot = None
            for _ in range(len(lv_doors) * 2):
                door = lv_doors[order[k % len(order)]]
                k += 1
                z_range = (max(door.z0, 0.9), min(door.z1, 2.15))
                spot = door.place(rng, pl.width, pl.height, z_range)
                if spot:
                    break
            if not spot:
                continue
            self.mount(pl.obj, door, *spot, rng.uniform(0.6, 1.4))
            pl.obj.color = (*lin(np.array([0.84, 0.85, 0.85]) * rng.uniform(0.9, 1.05)), rng.uniform(0.3, 0.6))
            color, emit = pl.texture.generate(rng, p)
            self.push(pl.color_img, color)
            self.push(pl.emit_img, np.concatenate([emit, np.ones(emit.shape[:2] + (1,), np.float32)], -1))
            bsdf = principled(pl.material.node_tree.nodes)
            bsdf.inputs["Roughness"].default_value = rng.uniform(0.25, 0.6)
            placed.append(pl)
        return placed

    def place_distractors(self, rng, doors):
        p = self.p
        self.device_emit = []
        lv_doors = [d for d in doors if d.lv] or doors
        main_doors = [d for d in doors if not d.lv] or doors
        for dev in self.devices[:int(rng.integers(p["devices"][0], p["devices"][1] + 1))]:
            w, h = rng.uniform(0.08, 0.32), rng.uniform(0.08, 0.3)
            door = lv_doors[rng.integers(len(lv_doors))] if rng.random() < 0.7 else doors[rng.integers(len(doors))]
            spot = door.place(rng, w, h)
            if not spot:
                continue
            d = rng.uniform(0.01, 0.08)
            dev.obj.location = (spot[0], door.front + d / 2, spot[1])
            dev.obj.scale = (w, d, h)
            dev.obj.rotation_euler = (0, 0, 0)
            dev.obj.color = (*lin(np.array([0.6, 0.6, 0.62]) * rng.uniform(0.4, 1.4)), 0.5)
            dev.obj.hide_render = False
            tw = 384
            color, emit = textures.generic_device(rng, self.glyphs, tw, max(32, int(tw * h / w)))
            self.push(dev.color_img, color)
            self.push(dev.emit_img, np.concatenate([emit, np.ones(emit.shape[:2] + (1,), np.float32)], -1))
            self.device_emit.append((dev.material, rng.uniform(0.5, 2)))
        for lab in self.labels:
            if rng.random() > p["label_item_prob"]:
                continue
            if lab.kind == "nameplate":
                w, h, door = rng.uniform(0.1, 0.25), rng.uniform(0.03, 0.07), main_doors[rng.integers(len(main_doors))]
            elif lab.kind == "tape":
                w, h, door = rng.uniform(0.08, 0.3), rng.uniform(0.03, 0.06), doors[rng.integers(len(doors))]
            else:
                s = rng.uniform(0.03, 0.08)
                w, h, door = s, s, doors[rng.integers(len(doors))]
            spot = door.place(rng, w, h)
            if not spot:
                continue
            lab.obj.location = (spot[0], door.front + 0.0008, spot[1])
            lab.obj.scale = (w, 0.0015, h)
            lab.obj.rotation_euler = (0, 0, rng.normal(0, 0.01) if lab.kind == "tape" else 0)
            lab.obj.color = (0.8, 0.8, 0.8, 0.5)
            lab.obj.hide_render = False
            tw = lab.color_img.size[0]
            self.push(lab.color_img, textures.nameplate(rng, self.glyphs, tw, max(16, int(tw * h / w)) if lab.kind != "sticker" else tw, lab.kind))
        for ob in self.vents:
            if rng.random() < p["vent_prob"]:
                w, h = rng.uniform(0.12, 0.35), rng.uniform(0.08, 0.3)
                door = main_doors[rng.integers(len(main_doors))]
                spot = door.place(rng, w, h)
                if spot:
                    self.set_box(ob, (spot[0], door.front + 0.002, spot[1]), (w, 0.004, h), (0.5, 0.5, 0.5), 0.5)
        for op in self.openings:
            if rng.random() < p["opening_prob"]:
                w, h = rng.uniform(0.08, 0.2), rng.uniform(0.08, 0.2)
                door = lv_doors[rng.integers(len(lv_doors))]
                spot = door.place(rng, w, h)
                if spot:
                    self.set_box(op.obj, (spot[0], door.front + 0.0005, spot[1]), (w, 0.001, h), (0.02, 0.02, 0.02), 0.9)
                    self.push(op.color_img, textures.opening(rng, 128, 128))
        for ob in self.small[:int(rng.integers(0, len(self.small) + 1))]:
            kind = rng.choice(["handle", "hinge", "lock", "plate"])
            door = doors[rng.integers(len(doors))]
            size = {"handle": (0.03, 0.04, 0.15), "hinge": (0.02, 0.015, 0.08), "lock": (0.04, 0.02, 0.04), "plate": (0.06, 0.005, 0.1)}[kind]
            spot = door.place(rng, size[0], size[2])
            if spot:
                col = lin((0.1, 0.1, 0.1)) if rng.random() < 0.6 else lin(np.array([0.6, 0.6, 0.6]) * rng.uniform(0.5, 1.4))
                self.set_box(ob, (spot[0], door.front + size[1] / 2, spot[1]), size, col, 0.4)
        for ob in self.knobs[:int(rng.integers(0, len(self.knobs) + 1))]:
            door = lv_doors[rng.integers(len(lv_doors))]
            r = rng.uniform(0.012, 0.03)
            spot = door.place(rng, 2 * r, 2 * r)
            if spot:
                col = [(0.8, 0.05, 0.05), (0.05, 0.6, 0.15), (0.05, 0.05, 0.05), (0.9, 0.75, 0.05), (0.85, 0.85, 0.85)][rng.integers(5)]
                d = rng.uniform(0.01, 0.04)
                ob.location = (spot[0], door.front + d / 2, spot[1])
                ob.scale = (2 * r, 2 * r, d)
                ob.color = (*lin(col), 0.3)
                ob.hide_render = False

    def pick_target(self, rng, placed, doors):
        rex = [pl for pl in placed if pl.kind == "rex615"]
        if rex:
            pl = rex[rng.integers(len(rex))]
            return np.array(pl.obj.location) + np.array([0, pl.obj.scale[1] * HOUSING_DEPTH, 0]), pl
        if placed and rng.random() < 0.5:
            pl = placed[rng.integers(len(placed))]
            return np.array(pl.obj.location), pl
        door = doors[rng.integers(len(doors))]
        return np.array([rng.uniform(door.x0, door.x1), door.front, rng.uniform(max(door.z0, 0.8), min(door.z1, 2.1))]), None

    def place_camera(self, rng, target):
        p = self.p
        point, pl = target
        fov = math.radians(rng.uniform(*p["fov_deg"]))
        f_px = 640 / math.tan(fov / 2)
        plate_w = pl.width if pl is not None else 0.262
        px = math.exp(rng.uniform(math.log(p["plate_px"][0]), math.log(p["plate_px"][1])))
        for _ in range(300):
            theta = math.radians(rng.uniform(0, 1) ** p["off_normal_power"] * p["off_normal_max_deg"])
            phi = rng.uniform(0, 2 * math.pi)
            d = np.array([math.sin(theta) * math.cos(phi), math.cos(theta), math.sin(theta) * math.sin(phi)])
            elev = math.degrees(math.asin(d[2]))
            if not p["elevation_deg"][0] <= elev <= p["elevation_deg"][1]:
                continue
            raw = f_px * plate_w * max(math.sqrt(1 - d[0] ** 2), 0.25) / px
            dist = float(np.clip(raw, *p["distance_m"]))
            pos = point + dist * d
            if dist == raw and p["camera_z"][0] <= pos[2] <= p["camera_z"][1]:
                break
        to = point - pos
        yaw = math.atan2(to[1], to[0])
        el = math.atan2(to[2], math.hypot(to[0], to[1]))
        half = fov / 2
        ang = math.atan(plate_w * 0.6 / max(dist, 0.3))
        margin = min(half * 0.95, ang) if rng.random() < p["full_view_prob"] else 0.0
        pitches = [math.radians(v) for v in p["camera_pitches_deg"]]
        ok = [q for q in pitches if abs(el - q) < half - margin]
        pitch = (ok[rng.integers(len(ok))] if ok else el + rng.uniform(-0.5, 0.5) * half) + math.radians(rng.uniform(-4, 4))
        pitch = float(np.clip(pitch, math.radians(-50), math.radians(50)))
        yaw += rng.uniform(-1, 1) * (half - margin) * 0.95
        cam = self.camera
        cam.data.angle = fov
        cam.rotation_euler = (math.pi / 2 + pitch, 0, yaw - math.pi / 2)
        rot = np.array(cam.rotation_euler.to_matrix())
        h = pl.height if pl is not None else 0.177
        corners = point + np.array([[sx * plate_w / 2, 0, sz * h / 2] for sx in (-1, 1) for sz in (-1, 1)])
        lo, hi = p["distance_m"]
        if abs(d[2]) > 1e-6:
            za, zb = sorted(((p["camera_z"][0] - point[2]) / d[2], (p["camera_z"][1] - point[2]) / d[2]))
            lo, hi = max(lo, za), min(hi, zb)
        for _ in range(2):
            pc = (corners - pos) @ rot
            if (pc[:, 2] > -0.05).any() or hi < lo:
                break
            x = pc[:, 0] / -pc[:, 2]
            width = (x.max() - x.min()) * f_px
            dist = float(np.clip(dist * width / px, lo, hi))
            pos = point + dist * d
        cam.location = pos
        return pos, fov

    def room_and_lights(self, rng, panels_x, top, cam, target):
        p = self.p
        x0 = min(panels_x[0], cam[0]) - rng.uniform(0.3, 3.0)
        x1 = max(panels_x[1], cam[0]) + rng.uniform(0.3, 3.0)
        y0, y1 = -0.85, max(cam[1], 1.5) + rng.uniform(0.5, 4.0)
        ceil = max(top + rng.uniform(0.3, 1.5), cam[2] + 0.3)
        self.set_box(self.room, ((x0 + x1) / 2, (y0 + y1) / 2, ceil / 2), (x1 - x0, y1 - y0, ceil))
        wall = lin(np.array([0.92, 0.91, 0.88]) * rng.uniform(0.7, 1.05))
        self.room_mats[0].inputs["Base Color"].default_value = (*wall, 1)
        self.room_mats[1].inputs["Base Color"].default_value = (*lin(np.array([0.5, 0.5, 0.5]) * rng.uniform(0.4, 1.5)), 1)
        self.room_mats[2].inputs["Base Color"].default_value = (*wall, 1)
        dark = rng.random() < p["dark_prob"]
        n = int(rng.integers(*p["lights"])) if not dark else int(rng.integers(0, 2))
        kelvin = rng.uniform(*p["kelvin"])
        total = 0.0
        for i in range(n):
            lo = self.lights[i]
            lx, ly = rng.uniform(x0 + 0.2, x1 - 0.2), rng.uniform(y0 + 0.3, y1 - 0.2)
            lo.location = (lx, ly, ceil - 0.06)
            lo.rotation_euler = (0, 0, rng.choice([0, math.pi / 2]))
            lo.data.size, lo.data.size_y = 1.2, 0.08
            energy = math.exp(rng.uniform(math.log(p["light_watts"][0]), math.log(p["light_watts"][1])))
            if dark:
                energy *= rng.uniform(0.02, 0.2)
            lo.data.energy = energy
            col = kelvin_rgb(kelvin + rng.normal(0, 150))
            lo.data.color = col
            lo.hide_render = False
            tube = self.tubes[i]
            self.set_box(tube, (lx, ly, ceil - 0.04), (1.2, 0.05, 0.03) if lo.rotation_euler.z == 0 else (0.05, 1.2, 0.03), col, energy / 2.4)
            dist = np.linalg.norm(np.array([lx, ly, ceil]) - target[0])
            total += energy / (4 * math.pi * dist ** 2)
        if dark and rng.random() < p["headlamp_prob"]:
            self.spot.location = cam + rng.normal(0, 0.1, 3)
            to = Vector(tuple(target[0] - self.spot.location))
            self.spot.rotation_euler = to.to_track_quat("-Z", "Y").to_euler()
            self.spot.data.energy = rng.uniform(5, 60)
            self.spot.data.spot_size = math.radians(rng.uniform(30, 80))
            self.spot.data.color = kelvin_rgb(rng.uniform(4000, 6500))
            self.spot.hide_render = False
            total += self.spot.data.energy / (4 * math.pi * max(np.linalg.norm(to), 0.5) ** 2)
        if rng.random() < p["point_light_prob"] or (n == 0 and self.spot.hide_render):
            self.point.location = (rng.uniform(x0, x1), rng.uniform(y0 + 0.5, y1), rng.uniform(0.5, ceil - 0.2))
            self.point.data.energy = rng.uniform(5, 150) * (0.1 if dark else 1)
            self.point.data.color = kelvin_rgb(rng.uniform(2700, 6000))
            self.point.hide_render = False
            total += self.point.data.energy / (4 * math.pi * max(np.linalg.norm(np.array(self.point.location) - target[0]), 0.5) ** 2)
        self.world_bg.inputs["Strength"].default_value = 0.0
        self.emit_scale = max(total, 1e-4)
        self.dark = dark

    def occluders(self, rng, placed, doors, panels_x, top, cam, target):
        p = self.p
        point = target[0]
        if rng.random() < p["tray_prob"]:
            self.set_box(self.tray, ((panels_x[0] + panels_x[1]) / 2, rng.uniform(0.1, 0.5), top + rng.uniform(0.15, 0.5)),
                         (panels_x[1] - panels_x[0] + rng.uniform(0, 2), 1, 1), lin((0.7, 0.72, 0.72)), 0.4)
        n_cables = int(rng.integers(1, p["cables_max"] + 1)) if rng.random() < p["cable_prob"] else 0
        for ob in self.cables[:n_cables]:
            cu = ob.data
            cu.bevel_depth = rng.uniform(*p["cable_radius"])
            ob.color = (*lin(CABLE_COLORS[rng.integers(len(CABLE_COLORS))]), 0.4)
            y = rng.uniform(0.04, 0.25)
            x = point[0] + rng.normal(0, p["cable_spread"])
            z_top = top + rng.uniform(0.1, 0.6)
            z_end = rng.uniform(-0.1, point[2] - 0.2) if rng.random() < 0.7 else z_top
            pts = []
            for t in np.linspace(0, 1, 5):
                pts.append((x + rng.normal(0, 0.06) + (rng.uniform(-0.4, 0.4) if t == 1 else 0),
                            y + rng.normal(0, 0.02),
                            z_top + (z_end - z_top) * t + (math.sin(t * math.pi) * rng.uniform(-0.5, 0) if z_end == z_top else 0)))
            for bp, co in zip(cu.splines[0].bezier_points, pts):
                bp.co = co
                bp.handle_left_type = bp.handle_right_type = "AUTO"
            ob.hide_render = False
        if rng.random() < p["glass_prob"]:
            y = rng.uniform(0.06, 0.18)
            if cam[1] > y + 0.1:
                x0 = point[0] - rng.uniform(0.3, 0.9)
                x1 = point[0] + rng.uniform(0.3, 0.9)
                z0, z1 = max(0.1, point[2] - rng.uniform(0.4, 1.2)), point[2] + rng.uniform(0.3, 0.6)
                self.set_box(self.glass, ((x0 + x1) / 2, y, (z0 + z1) / 2), (x1 - x0, 0.004, z1 - z0))
                self.glass_bsdf.inputs["Roughness"].default_value = rng.uniform(0, 0.04)
                tint = rng.uniform(0.9, 1.0)
                self.glass_bsdf.inputs["Color"].default_value = (tint * 0.97, tint, tint * 0.98, 1)
                col = lin(np.array([0.8, 0.8, 0.8]) * rng.uniform(0.3, 1.1))
                t = 0.03
                for ob, c, s in zip(self.glass_frame,
                                    [((x0 + x1) / 2, y, z1 + t / 2), ((x0 + x1) / 2, y, z0 - t / 2), (x0 - t / 2, y, (z0 + z1) / 2), (x1 + t / 2, y, (z0 + z1) / 2)],
                                    [(x1 - x0 + 2 * t, 0.02, t), (x1 - x0 + 2 * t, 0.02, t), (t, 0.02, z1 - z0), (t, 0.02, z1 - z0)]):
                    self.set_box(ob, c, s, col, 0.5)

    def finish_emission(self, rng):
        for pl in self.plates:
            principled(pl.material.node_tree.nodes).inputs["Emission Strength"].default_value = self.emit_scale * rng.uniform(*self.p["emission_scale"])
        for mat, k in self.device_emit:
            principled(mat.node_tree.nodes).inputs["Emission Strength"].default_value = self.emit_scale * k
