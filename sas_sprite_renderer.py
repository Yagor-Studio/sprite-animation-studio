# ============================================================
#  SAS Sprite Renderer - Blender Addon  (v0.2.0)
#  Genera sprite 8-angoli compatibili con "Sprite Animation Studio"
#
#  Naming: [SPRITE_CODE 2][ANIM_CODE 2][FRAME_LETTER][ANGLE].png
# ============================================================

bl_info = {
    "name": "SAS Sprite Renderer",
    "author": "Yagor Studio",
    "version": (0, 4, 3),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > SAS",
    "description": "Render 8-camera sprites compatibili con Sprite Animation Studio",
    "category": "Render",
}

import bpy
import os
import math
import json
from datetime import datetime
from mathutils import Vector
from bpy.props import (
    BoolProperty, StringProperty, IntProperty, FloatProperty,
    EnumProperty, PointerProperty, FloatVectorProperty
)
from bpy.types import Panel, Operator, PropertyGroup

_live_last_signature = None

# ============================================================
#  HELPERS
# ============================================================

def get_initials(name):
    name = (name or "").strip()
    if not name:
        return "XX"
    words = name.split()
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return name[:2].upper().ljust(2, 'X')


def frame_letter(idx):
    if idx < 0 or idx > 25:
        return None
    return chr(ord('A') + idx)


def camera_position(angle_num, distance, height, center):
    theta = math.radians(270 + (angle_num - 1) * 45)
    x = distance * math.cos(theta)
    y = distance * math.sin(theta)
    return Vector((center.x + x, center.y + y, center.z + height))


def ensure_collection(name):
    scene = bpy.context.scene
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        scene.collection.children.link(coll)
    return coll


def point_at(cam_obj, target_loc):
    direction = target_loc - cam_obj.location
    if direction.length < 1e-6:
        return
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot_quat.to_euler()

def _refresh_cameras(context):
    if context is None or context.scene is None:
        return
    if bpy.data.objects.get("SAS_Cam_1") is None:
        return
    s = context.scene.sas_settings
    if not s.target:
        return

    # Anello: SEMPRE centrato sul target (non si muove)
    ring_center = s.target.matrix_world.translation
    # Mira: il punto verso cui le camere guardano (si può spostare)
    aim_point = ring_center + s.look_at_offset

    for angle_num in range(1, 9):
        cam = bpy.data.objects.get(f"SAS_Cam_{angle_num}")
        if cam is None:
            continue

        cam.location = camera_position(angle_num, s.cam_distance, s.cam_height, ring_center)
        point_at(cam, aim_point)

        d = cam.data
        d.type = s.cam_type
        if s.cam_type == 'PERSP':
            d.lens = s.focal_length * s.cam_zoom
        else:
            d.ortho_scale = s.ortho_scale / max(0.001, s.cam_zoom)
        d.shift_x = s.cam_shift_x
        d.shift_y = s.cam_shift_y
        d.sensor_fit = 'HORIZONTAL'


def get_frames_to_render(scene, source):
    if source == "MARKERS":
        frames = sorted({m.frame for m in scene.timeline_markers})
        if frames:
            return frames
    return list(range(scene.frame_start, scene.frame_end + 1))


def resolve_output_dir(raw):
    """Risolve il percorso di output in modo robusto.

    Se il .blend non è stato ancora salvato, '//' diventa un percorso
    UNC non valido su Windows -> fallback in home utente.
    """
    raw = (raw or "").strip()
    if not raw:
        raw = "//sas_render/"

    if raw.startswith("//"):
        if bpy.data.filepath:
            # blend salvato -> risoluzione normale
            return bpy.path.abspath(raw)
        # blend NON salvato -> fallback sicuro
        tail = raw[2:].lstrip("/\\")
        fallback = os.path.join(os.path.expanduser("~"), tail or "sas_render")
        return fallback

    return bpy.path.abspath(raw)


# ============================================================
#  PROPERTIES
# ============================================================

class SAS_Settings(PropertyGroup):

    # --- Naming ---
    sas_compatible: BoolProperty(
        name="SAS Compatible",
        default=True,
    )
    sprite_name: StringProperty(name="Nome Sprite", default="")
    anim_name: StringProperty(name="Nome Animazione", default="")
    death_sprite: BoolProperty(name="Sprite 0", default=False)
    # --- Framing / obiettivo ---
    cam_zoom: FloatProperty(
        name="Zoom",
        description="Moltiplicatore di ingrandimento (1.0 = neutro)",
        default=1.0, min=0.1, max=5.0,
        soft_min=0.25, soft_max=3.0,
        update=lambda self, ctx: _refresh_cameras(ctx),
    )
    cam_shift_x: FloatProperty(
        name="Shift X",
        description="Scorrimento orizzontale del frame (-1 … +1)",
        default=0.0, min=-1.0, max=1.0,
        update=lambda self, ctx: _refresh_cameras(ctx),
    )
    cam_shift_y: FloatProperty(
        name="Shift Y",
        description="Scorrimento verticale del frame (-1 … +1)",
        default=0.0, min=-1.0, max=1.0,
        update=lambda self, ctx: _refresh_cameras(ctx),
    )
    look_at_offset: FloatVectorProperty(
        name="Punto di mira",
        description="Offset (X,Y,Z) del punto che le telecamere inquadrano, "
                    "relativo alla posizione del target. "
                    "Alza Z per inquadrare la testa, abbassa per i piedi.",
        subtype='TRANSLATION',
        default=(0.0, 0.0, 0.0),
        size=3,
        soft_min=-2.0,   # ← nuovo
        soft_max=2.0,    # ← nuovo
        update=lambda self, ctx: _refresh_cameras(ctx),
    )
    default_duration_ms: IntProperty(
        name="Durata frame (ms)",
        description="Durata in ms di ciascun frame (112 = 4 tick @ 35Hz, default SAS)",
        default=112, min=1, max=10000,
    )
    fps: IntProperty(
        name="Frame Rate",
        description="Frame al secondo. Usato per duration_ms nel manifest (1000/fps)",
        default=24, min=1, max=120,
    )
    duration_source: EnumProperty(
        name="Durata frame",
        items=[
            ("FPS", "Da Frame Rate", "duration_ms = 1000 / fps"),
            ("MS",  "Millisecondi", "Usa il valore ms esplicito"),
        ],
        default="FPS",
    )


    # --- Target / Camera ---
    follow_target: BoolProperty(
        name="Insegui target durante il render",
        description="Se attivo, le camere si riallineano ad ogni frame "
                    "per seguire il target. Utile per soggetti statici. "
                    "Disattivare per animazioni con movimento visibile.",
        default=False,
    )
    target: PointerProperty(
        name="Target",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type in {'EMPTY', 'MESH', 'ARMATURE'},
    )
    cam_distance: FloatProperty(
        name="Distanza", default=5.0, min=0.1, soft_max=50.0,
        update=lambda self, ctx: _refresh_cameras(ctx),
    )
    cam_height: FloatProperty(
        name="Altezza", default=1.5, soft_min=-10.0, soft_max=10.0,
        update=lambda self, ctx: _refresh_cameras(ctx),
    )
    cam_type: EnumProperty(
        name="Tipo",
        items=[("PERSP", "Prospettica", ""), ("ORTHO", "Ortografica", "")],
        default="PERSP",
        update=lambda self, ctx: _refresh_cameras(ctx),
    )
    focal_length: FloatProperty(
        name="Focale (mm)", default=50.0, min=1.0, max=500.0,
        update=lambda self, ctx: _refresh_cameras(ctx),
    )
    ortho_scale: FloatProperty(
        name="Ortho Scale", default=2.0, min=0.01, soft_max=100.0,
        update=lambda self, ctx: _refresh_cameras(ctx),
    )
    focal_length: FloatProperty(name="Focale (mm)", default=50.0, min=1.0, max=500.0)
    ortho_scale: FloatProperty(name="Ortho Scale", default=2.0, min=0.01, soft_max=100.0)

    # --- Frames ---
    frame_source: EnumProperty(
        name="Sorgente frame",
        items=[
            ("RANGE", "Scene Range", "Da frame_start a frame_end"),
            ("MARKERS", "Timeline Markers", "Un marker = una posa (frame letter)"),
        ],
        default="RANGE",
    )

    # --- Live mode ---
    live_enabled: BoolProperty(
        name="Live Mode",
        description="Renderizza periodicamente il frame corrente dal viewport",
        default=False,
    )
    live_interval: FloatProperty(
        name="Intervallo (s)",
        description="Secondi tra un aggiornamento e l'altro",
        default=1.0, min=0.2, max=30.0,
    )
    live_quality: EnumProperty(
        name="Qualità Live",
        items=[
            ("HIGH",   "High",   "Material preview, risoluzione piena (più lento)"),
            ("MEDIUM", "Medium", "Solid con colori materiale, risoluzione piena"),
            ("LOW",    "Low",    "Solid, risoluzione dimezzata (velocissimo)"),
        ],
        default="MEDIUM",
    )
    live_eevee_samples: IntProperty(
        name="Campioni live",
        description="Campioni EEVEE/Cycles usati solo durante la Live. "
                    "0 = usa i campioni di scena (render finale).",
        default=8, min=0, max=512,
    )
    live_camera_scope: EnumProperty(
        name="Ambito",
        items=[
            ("ALL", "Tutti gli 8 angoli", "Aggiorna tutti gli angoli del frame"),
            ("ACTIVE", "Solo camera attiva", "Aggiorna solo l'angolo della camera attualmente selezionata"),
        ],
        default="ALL",
    )

    # --- Output ---
    output_dir: StringProperty(
        name="Cartella output",
        default="//sas_render/",
        subtype='DIR_PATH',
    )
    res_x: IntProperty(name="Risoluzione X", default=128, min=1, max=4096)
    res_y: IntProperty(name="Risoluzione Y", default=128, min=1, max=4096)
    use_transparent: BoolProperty(name="Sfondo trasparente", default=True)

    # --- Opzioni ---
    keep_cameras: BoolProperty(
        name="Mantieni telecamere dopo il render",
        default=True,
    )


# ============================================================
#  OPERATORS
# ============================================================

class SAS_OT_create_target(Operator):
    bl_idname = "sas.create_target"
    bl_label = "Crea Empty Target"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.sas_settings
        loc = context.scene.cursor.location.copy()
        if context.selected_objects:
            loc = context.selected_objects[0].matrix_world.translation.copy()

        empty = bpy.data.objects.new("SAS_Target", None)
        empty.empty_display_type = 'SPHERE'
        empty.empty_display_size = 0.2
        empty.location = loc
        context.scene.collection.objects.link(empty)

        s.target = empty
        self.report({'INFO'}, f"Target creato a {tuple(round(v,2) for v in loc)}")
        return {'FINISHED'}


class SAS_OT_setup_cameras(Operator):
    bl_idname = "sas.setup_cameras"
    bl_label = "Setup 8 Telecamere"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.sas_settings
        if not s.target:
            self.report({'ERROR'}, "Seleziona un Target prima")
            return {'CANCELLED'}

        coll = ensure_collection("SAS_Cameras")

        # --- Due centri distinti ---
        # ring_center: dove sta l'ANELLO delle camere (ancorato al target)
        # aim_point:   dove GUARDANO le camere (target + offset di mira)
        ring_center = s.target.matrix_world.translation
        aim_point = ring_center + s.look_at_offset

        created = 0
        for angle_num in range(1, 9):
            name = f"SAS_Cam_{angle_num}"
            cam_obj = bpy.data.objects.get(name)

            # Crea la camera se non esiste
            if cam_obj is None or cam_obj.type != 'CAMERA':
                cam_data = bpy.data.cameras.new(name=name)
                cam_obj = bpy.data.objects.new(name, object_data=cam_data)
                coll.objects.link(cam_obj)
                created += 1
            else:
                # Assicurati che sia nella collection giusta
                if cam_obj.name not in coll.objects:
                    for c in list(cam_obj.users_collection):
                        c.objects.unlink(cam_obj)
                    coll.objects.link(cam_obj)

            # --- Posizionamento ---
            # L'anello usa SEMPRE ring_center (non si sposta col punto di mira)
            cam_obj.location = camera_position(
                angle_num, s.cam_distance, s.cam_height, ring_center
            )
            # La mira usa aim_point (che può essere spostato)
            point_at(cam_obj, aim_point)

            # --- Obiettivo ---
            d = cam_obj.data
            d.type = s.cam_type
            if s.cam_type == 'PERSP':
                d.lens = s.focal_length * s.cam_zoom
            else:
                d.ortho_scale = s.ortho_scale / max(0.001, s.cam_zoom)

            # Regole della camera valide per entrambi i tipi di obiettivo
            d.shift_x = s.cam_shift_x
            d.shift_y = s.cam_shift_y
            d.sensor_fit = 'HORIZONTAL'

        # Rendi visibile la cam 1 come attiva (così la vedi subito)
        cam1 = bpy.data.objects.get("SAS_Cam_1")
        if cam1:
            context.scene.camera = cam1

        coll.hide_viewport = False
        coll.hide_render = False

        if created:
            self.report({'INFO'}, f"{created} telecamere create in 'SAS_Cameras'")
        else:
            self.report({'INFO'}, "Telecamere aggiornate")
        return {'FINISHED'}


class SAS_OT_clear_cameras(Operator):
    bl_idname = "sas.clear_cameras"
    bl_label = "Elimina Telecamere"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        coll = bpy.data.collections.get("SAS_Cameras")
        if coll:
            for obj in list(coll.objects):
                if obj.type == 'CAMERA':
                    bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.collections.remove(coll)
        return {'FINISHED'}


class SAS_OT_render_all(Operator):
    bl_idname = "sas.render_all"
    bl_label = "Render All"
    bl_options = {'REGISTER'}

    def execute(self, context):
        s = context.scene.sas_settings
        scene = context.scene
        # ---------- PREPARAZIONE BATCH ----------
        if s.live_enabled:
            bpy.ops.sas.live_stop()
            self.report({'INFO'}, "Live Mode fermata per il render batch")
        # ---------- VALIDAZIONE ----------
        if not s.target:
            self.report({'ERROR'}, "Target non impostato")
            return {'CANCELLED'}

        if s.sas_compatible:
            if not s.sprite_name.strip():
                self.report({'ERROR'}, "Nome Sprite vuoto")
                return {'CANCELLED'}
            if not s.anim_name.strip():
                self.report({'ERROR'}, "Nome Animazione vuoto")
                return {'CANCELLED'}

        # ---------- CARTELLA OUTPUT (robusta) ----------
        try:
            out_dir = resolve_output_dir(s.output_dir)
        except Exception as e:
            self.report({'ERROR'}, f"Percorso output non valido: {e}")
            return {'CANCELLED'}

        try:
            os.makedirs(out_dir, exist_ok=True)
        except PermissionError:
            self.report(
                {'ERROR'},
                f"Permesso negato su '{out_dir}'. "
                f"Salva il .blend oppure imposta una cartella output scrivibile."
            )
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Impossibile creare la cartella: {e}")
            return {'CANCELLED'}

        # Verifica scrivibilità
        if not os.access(out_dir, os.W_OK):
            self.report({'ERROR'}, f"Cartella non scrivibile: {out_dir}")
            return {'CANCELLED'}

        # ---------- CODICI ----------
        sprite_code = get_initials(s.sprite_name) if s.sas_compatible else ""
        anim_code = get_initials(s.anim_name) if s.sas_compatible else ""

        # ---------- SETUP TELECAMERE (solo se non esistono) ----------
        if bpy.data.objects.get("SAS_Cam_1") is None:
            bpy.ops.sas.setup_cameras()

        # ---------- SALVA STATO ----------
        prev_cam = scene.camera
        prev_path = scene.render.filepath
        prev_x = scene.render.resolution_x
        prev_y = scene.render.resolution_y
        prev_pct = scene.render.resolution_percentage
        prev_film = scene.render.film_transparent
        prev_fmt = scene.render.image_settings.file_format
        prev_mode = scene.render.image_settings.color_mode

        # ---------- CONFIG RENDER ----------
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_mode = 'RGBA'
        scene.render.resolution_x = s.res_x
        scene.render.resolution_y = s.res_y
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = s.use_transparent

        # ---------- DETERMINA ANGOLI ----------
        if s.sas_compatible and s.death_sprite:
            angles = [0]
        else:
            angles = list(range(1, 9))

        # ---------- RENDER LOOP ----------
        frames = get_frames_to_render(scene, s.frame_source)
        total_rendered = 0
        overflow = 0

        manifest_frames = []

        try:
            for idx, frame_num in enumerate(frames):
                letter = frame_letter(idx)
                if letter is None:
                    overflow += 1
                    continue

                scene.frame_set(frame_num)
                if s.follow_target:
                    _refresh_cameras(context)

                frame_angles = []
                for angle in angles:
                    cam_name = "SAS_Cam_1" if angle == 0 else f"SAS_Cam_{angle}"
                    cam = bpy.data.objects.get(cam_name)
                    if not cam:
                        continue

                    scene.camera = cam

                    if s.sas_compatible:
                        filename = f"{sprite_code}{anim_code}{letter}{angle}.png"
                    else:
                        filename = f"{letter}{angle}.png"

                    scene.render.filepath = os.path.join(out_dir, filename)
                    bpy.ops.render.render(write_still=True)
                    total_rendered += 1

                    frame_angles.append({
                        "angle": angle,
                        "file": filename,
                    })

                manifest_frames.append({
                    "letter": letter,
                    "duration_ms": int(s.default_duration_ms),
                    "angles": frame_angles,
                })

            # ---------- MANIFEST (solo a batch completato) ----------
            if s.sas_compatible and manifest_frames:
                manifest = {
                    "version": "1.0",
                    "source": "blender_sas_addon",
                    "timestamp": datetime.now().isoformat(),
                    "sprite": {
                        "name": s.sprite_name,
                        "code": sprite_code,
                    },
                    "animation": {
                        "name": s.anim_name,
                        "code": anim_code,
                        "loop": True,
                        "anchor": "bottom",
                    },
                    "output_dir": out_dir,
                    "death_sprite": bool(s.death_sprite),
                    "frames": manifest_frames,
                }
                try:
                    write_manifest_atomic(out_dir, manifest)
                except Exception as e:
                    self.report({'WARNING'}, f"Manifest non scritto: {e}")

        finally:
            # ---------- RIPRISTINA STATO ----------
            scene.camera = prev_cam
            scene.render.filepath = prev_path
            scene.render.resolution_x = prev_x
            scene.render.resolution_y = prev_y
            scene.render.resolution_percentage = prev_pct
            scene.render.film_transparent = prev_film
            scene.render.image_settings.file_format = prev_fmt
            scene.render.image_settings.color_mode = prev_mode

            if not s.keep_cameras:
                bpy.ops.sas.clear_cameras()

        # ---------- REPORT ----------
        msg = f"Renderizzati {total_rendered} file in {out_dir}"
        if overflow:
            msg += f"  |  {overflow} frame ignorati (indice > 25)"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class SAS_OT_use_home_dir(Operator):
    """Imposta la cartella output a una directory sicura nella home utente."""
    bl_idname = "sas.use_home_dir"
    bl_label = "Usa cartella Home"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.sas_settings
        home_dir = os.path.join(os.path.expanduser("~"), "sas_render")
        s.output_dir = home_dir + os.sep
        self.report({'INFO'}, f"Output: {home_dir}")
        return {'FINISHED'}


class SAS_OT_use_blend_dir(Operator):
    """Imposta la cartella output accanto al file .blend salvato."""
    bl_idname = "sas.use_blend_dir"
    bl_label = "Accanto al .blend"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.sas_settings
        if not bpy.data.filepath:
            self.report({'ERROR'}, "Salva prima il file .blend")
            return {'CANCELLED'}
        blend_dir = os.path.dirname(bpy.data.filepath)
        out = os.path.join(blend_dir, "sas_render")
        s.output_dir = out + os.sep
        self.report({'INFO'}, f"Output: {out}")
        return {'FINISHED'}

class SAS_OT_preview_view(Operator):
    bl_idname = "sas.preview_view"
    bl_label = "Anteprima (viewport = render)"
    bl_description = (
        "Applica risoluzione SAS alla scena, attiva SAS_Cam_1 come camera "
        "e imposta sensor_fit coerente. Poi premi 0 per vedere il PNG finale."
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.sas_settings
        scene = context.scene

        # Assicura che le camere esistano
        if bpy.data.objects.get("SAS_Cam_1") is None:
            bpy.ops.sas.setup_cameras()

        # Applica risoluzione SAS alla scena
        scene.render.resolution_x = s.res_x
        scene.render.resolution_y = s.res_y
        scene.render.resolution_percentage = 100
        # Frame rate
        scene.render.fps = s.fps
        scene.render.fps_base = 1.0
        # Camera 1 attiva
        cam1 = bpy.data.objects.get("SAS_Cam_1")
        if cam1:
            scene.camera = cam1

        # sensor_fit: per render quadrati AUTO è ambiguo, HORIZONTAL è deterministico
        for i in range(1, 9):
            c = bpy.data.objects.get(f"SAS_Cam_{i}")
            if c:
                c.data.sensor_fit = 'HORIZONTAL'

        self.report({'INFO'}, "Ora premi 0 (numpad) per entrare in camera view")
        return {'FINISHED'}


class SAS_OT_restore_resolution(Operator):
    bl_idname = "sas.restore_resolution"
    bl_label = "Ripristina risoluzione scena"
    bl_description = "Riporta la risoluzione della scena a un valore ampio per lavorare comodamente"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.render.resolution_x = 1920
        context.scene.render.resolution_y = 1080
        context.scene.render.resolution_percentage = 100
        self.report({'INFO'}, "Risoluzione scena ripristinata a 1920x1080")
        return {'FINISHED'}
# ============================================================
#  UI PANELS
# ============================================================

class SAS_PT_main(Panel):
    bl_label = "SAS Sprite Renderer"
    bl_idname = "SAS_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SAS"

    def draw(self, context):
        layout = self.layout
        s = context.scene.sas_settings
        # Avviso se la risoluzione di scena non corrisponde a quella SAS
        scene = context.scene
        if (scene.render.resolution_x != s.res_x or
                scene.render.resolution_y != s.res_y):
            warn = layout.box()
            warn.label(
                text=f"⚠ Viewport {scene.render.resolution_x}×{scene.render.resolution_y} "
                     f"≠ SAS {s.res_x}×{s.res_y}",
                icon='ERROR'
            )
            warn.label(text="Premi 'Anteprima' per allineare viewport e render")

        # Live mode
        box = layout.box()
        box.label(text="Live Mode", icon='PLAY')
        box.prop(s, "live_quality", text="")
        if s.live_quality == 'HIGH':
            box.prop(s, "live_eevee_samples")
        box.prop(s, "live_camera_scope", text="")
        row = box.row(align=True)
        row.prop(s, "live_interval")
        if s.live_enabled:
            row.operator("sas.live_stop", icon='PAUSE', text="")
        else:
            row.operator("sas.live_start", icon='PLAY', text="")
        if s.live_enabled:
            box.label(text="● attivo", icon='RADIOBUT_ON')

        # ===== QUICK RENDER (sempre visibile in cima) =====
        box = layout.box()
        col = box.column(align=True)

        if s.sas_compatible and s.sprite_name and s.anim_name:
            sprite_code = get_initials(s.sprite_name)
            anim_code = get_initials(s.anim_name)
            if s.death_sprite:
                preview = f"{sprite_code}{anim_code}A0.png"
            else:
                preview = f"{sprite_code}{anim_code}A1.png … {sprite_code}{anim_code}A8.png"
            col.label(text=f"→ {preview}", icon='FILE_IMAGE')
        elif not s.sas_compatible:
            col.label(text="→ A1.png … Z8.png", icon='FILE_IMAGE')
        else:
            col.label(text="⚠ Compila Naming", icon='ERROR')

        # Cartella output + scorciatoie
        row = col.row(align=True)
        row.prop(s, "output_dir", text="")
        row.operator("sas.use_home_dir", text="", icon='HOME')
        row.operator("sas.use_blend_dir", text="", icon='FILE_BLEND')

        # Render
        row = col.row()
        row.scale_y = 1.8
        row.operator("sas.render_all", icon='RENDER_STILL', text="RENDER ALL")
    
        # Anteprima
        row = col.row(align=True)
        row.operator("sas.preview_view", icon='VIEW_CAMERA', text="Anteprima")
        row.operator("sas.restore_resolution", icon='LOOP_BACK', text="")

        # Setup camera
        row = col.row(align=True)
        row.operator("sas.setup_cameras", icon='CAMERA_DATA', text="Setup 8 Cam")
        row.operator("sas.clear_cameras", icon='X', text="Pulisci")


class SAS_PT_naming(Panel):
    bl_label = "Naming"
    bl_idname = "SAS_PT_naming"
    bl_parent_id = "SAS_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SAS"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        s = context.scene.sas_settings

        layout.prop(s, "sas_compatible")

        if s.sas_compatible:
            col = layout.column(align=True)
            col.prop(s, "sprite_name")
            col.prop(s, "anim_name")
            layout.prop(s, "death_sprite")

            if not s.sprite_name.strip() or not s.anim_name.strip():
                layout.label(text="⚠ Nomi obbligatori", icon='ERROR')


class SAS_PT_camera(Panel):
    bl_label = "Target & Camera"
    bl_idname = "SAS_PT_camera"
    bl_parent_id = "SAS_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SAS"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        s = context.scene.sas_settings

        # --- Target ---
        row = layout.row(align=True)
        row.prop(s, "target", text="")
        row.operator("sas.create_target", text="", icon='ADD')

        # --- Inquadratura ---
        box = layout.box()
        box.label(text="Inquadratura", icon='VIEW_CAMERA')
        col = box.column(align=True)
        col.prop(s, "cam_distance")
        col.prop(s, "cam_height")
        col.prop(s, "cam_zoom")
        col.prop(s, "cam_shift_x")
        col.prop(s, "cam_shift_y")
        box.prop(s, "look_at_offset")
        box.prop(s, "follow_target")

        # --- Obiettivo ---
        box = layout.box()
        box.label(text="Obiettivo", icon='CAMERA_DATA')
        col = box.column(align=True)
        col.prop(s, "cam_type", text="")
        if s.cam_type == 'PERSP':
            col.prop(s, "focal_length")
            eff = s.focal_length * s.cam_zoom
            box.label(text=f"Focale effettiva: {eff:.1f} mm", icon='INFO')
        else:
            col.prop(s, "ortho_scale")
            eff = s.ortho_scale / max(0.001, s.cam_zoom)
            box.label(text=f"Ortho effettivo: {eff:.3f}", icon='INFO')

        # --- Azioni ---
        layout.separator()
        row = layout.row(align=True)
        row.operator("sas.setup_cameras", text="Setup / Aggiorna", icon='FILE_REFRESH')

        layout.prop(s, "keep_cameras")


class SAS_PT_frames(Panel):
    bl_label = "Frames"
    bl_idname = "SAS_PT_frames"
    bl_parent_id = "SAS_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SAS"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        s = context.scene.sas_settings

        layout.prop(s, "frame_source", text="")
        col = layout.column(align=True)
        col.prop(context.scene, "frame_start", text="Start")
        col.prop(context.scene, "frame_end", text="End")
        layout.prop(s, "duration_source", text="")
        if s.duration_source == 'FPS':
            layout.prop(s, "fps")
        else:
            layout.prop(s, "default_duration_ms")
        
class SAS_OT_live_start(Operator):
    bl_idname = "sas.live_start"
    bl_label = "Avvia Live"
    bl_description = "Avvia l'aggiornamento periodico del frame corrente"

    def execute(self, context):
        global _live_last_signature
        _live_last_signature = None
        
        s = context.scene.sas_settings
        s.live_enabled = True
        # Ri-registra il timer se non è già attivo
        try:
            bpy.app.timers.unregister(_live_tick)
        except (ValueError, TypeError):
            pass
        bpy.app.timers.register(_live_tick, first_interval=0.1)
        self.report({'INFO'}, f"Live attivo ogni {s.live_interval:.1f}s")
        return {'FINISHED'}
        


class SAS_OT_live_stop(Operator):
    bl_idname = "sas.live_stop"
    bl_label = "Ferma Live"

    def execute(self, context):
        s = context.scene.sas_settings
        s.live_enabled = False
        try:
            bpy.app.timers.unregister(_live_tick)
        except (ValueError, TypeError):
            pass
        self.report({'INFO'}, "Live fermato")
        return {'FINISHED'}

class SAS_PT_output(Panel):
    bl_label = "Output"
    bl_idname = "SAS_PT_output"
    bl_parent_id = "SAS_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SAS"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        s = context.scene.sas_settings

        layout.prop(s, "output_dir", text="")
        row = layout.row(align=True)
        row.operator("sas.use_home_dir", text="Home")
        row.operator("sas.use_blend_dir", text="Accanto .blend")

        row = layout.row(align=True)
        row.prop(s, "res_x")
        row.prop(s, "res_y")
        layout.prop(s, "use_transparent")


class SAS_PT_help(Panel):
    bl_label = "Help — Naming Convention"
    bl_idname = "SAS_PT_help"
    bl_parent_id = "SAS_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SAS"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        lines = [
            ("— FORMATO NOME FILE —", None),
            ("[SPRITE][ANIM][FRAME][ANGLE].png", None),
            ("", None),
            ("SPRITE = 2 lettere dal nome sprite", None),
            ("  'Doom Guy'  → 'DG'", None),
            ("  'Hero'      → 'HE' (fallback)", None),
            ("ANIM   = 2 lettere dal nome animazione", None),
            ("  'Walking Animation' → 'WA'", None),
            ("FRAME  = A, B, C, … (max 26)", None),
            ("ANGLE  = 1..8  (indice camera)", None),
            ("  1 = frontale, 5 = posteriore", None),
            ("  0 = solo frontale (sprite di morte)", None),
            ("", None),
            ("— ESEMPIO —", None),
            ("  'Doom Guy' + 'Walking Animation'", None),
            ("  Frame A, angle 1 → DGWAA1.png", None),
            ("  Death, Frame A   → DGWAA0.png", None),
        ]
        for text, _ in lines:
            if text.startswith("—"):
                col.label(text=text, icon='INFO')
            elif text == "":
                col.separator(factor=0.3)
            else:
                col.label(text=text)


# ============================================================
#  REGISTRATION
# ============================================================

classes = (
    SAS_Settings,
    SAS_OT_create_target,
    SAS_OT_setup_cameras,
    SAS_OT_clear_cameras,
    SAS_OT_render_all,
    SAS_OT_use_home_dir,
    SAS_OT_use_blend_dir,
    SAS_PT_main,
    SAS_PT_naming,
    SAS_PT_camera,
    SAS_PT_frames,
    SAS_PT_output,
    SAS_PT_help,
    SAS_OT_preview_view,
    SAS_OT_restore_resolution,
    SAS_OT_live_start,
    SAS_OT_live_stop,
)

def write_manifest_atomic(out_dir, manifest):
    """Scrive manifest.json in modo atomico (tmp + rename)."""
    manifest_path = os.path.join(out_dir, "manifest.json")
    tmp_path = manifest_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, manifest_path)   # atomico su Windows e Unix

def _apply_live_quality(quality, use_real_engine=False, live_samples=0):
    scene = bpy.context.scene
    shading = scene.display.shading
    prev = (
        shading.type, shading.color_type,
        scene.render.resolution_x, scene.render.resolution_y,
        scene.eevee.taa_render_samples,      # ← nuovo
        scene.cycles.samples,                # ← nuovo
    )
    try:
        if use_real_engine:
            if live_samples > 0:
                scene.eevee.taa_render_samples = live_samples
                scene.cycles.samples = live_samples
            print(f"[SAS live] quality=HIGH samples={live_samples or 'scene default'}")
        elif quality == 'MEDIUM':
            shading.type = 'SOLID'
            shading.color_type = 'MATERIAL'
        else:  # LOW
            shading.type = 'SOLID'
            shading.color_type = 'MATERIAL'
            scene.render.resolution_x = max(1, scene.render.resolution_x // 2)
            scene.render.resolution_y = max(1, scene.render.resolution_y // 2)
    except Exception as e:
        print(f"[SAS live] quality apply failed: {e}")
    return prev


def _restore_live_quality(prev):
    try:
        scene = bpy.context.scene
        shading = scene.display.shading
        shading.type = prev[0]
        shading.color_type = prev[1]
        scene.render.resolution_x = prev[2]
        scene.render.resolution_y = prev[3]
        scene.eevee.taa_render_samples = prev[4]
        scene.cycles.samples = prev[5]
    except Exception as e:
        print(f"[SAS live] quality restore failed: {e}")


def _render_still(out_path, real_engine=False):
    """Renderizza un singolo frame in out_path.

    real_engine=False -> OpenGL viewport (veloce, preview)
    real_engine=True  -> motore di render vero (Cycles/Eevee, lento ma fedele)
    """
    scene = bpy.context.scene
    prev_path = scene.render.filepath
    scene.render.filepath = out_path
    try:
        if real_engine:
            bpy.ops.render.render(write_still=True)
        else:
            bpy.ops.render.opengl(write_still=True, view_context=False)
    except RuntimeError as e:
        mode = "engine" if real_engine else "gl"
        print(f"[SAS live] render fallito ({mode}): {e}")
        return False
    finally:
        scene.render.filepath = prev_path
    exists = os.path.exists(out_path)
    print(f"[SAS live]   -> {out_path}  (exists={exists})")
    return exists


def _angle_from_camera_name(cam_name):
    """'SAS_Cam_3' -> 3, altrimenti None."""
    if not cam_name or not cam_name.startswith("SAS_Cam_"):
        return None
    try:
        return int(cam_name.split("_")[-1])
    except (ValueError, IndexError):
        return None


def render_live_frame():
    """Renderizza il frame corrente e scrive manifest 'live'.

    Non lancia eccezioni: qualsiasi problema viene loggato e ignorato,
    così il timer continua a girare.
    """
    try:
        scene = bpy.context.scene
        s = scene.sas_settings
    except Exception:
        return

    if not s.sas_compatible:
        return
    if not s.sprite_name.strip() or not s.anim_name.strip():
        return
    if not s.target:
        return
    # Le camere devono esistere
    if bpy.data.objects.get("SAS_Cam_1") is None:
        return
    if s.follow_target:
        _refresh_cameras(bpy.context)

    try:
        out_dir = resolve_output_dir(s.output_dir)
        os.makedirs(out_dir, exist_ok=True)
    except Exception as e:
        print(f"[SAS live] output non valido: {e}")
        return

    sprite_code = get_initials(s.sprite_name)
    anim_code = get_initials(s.anim_name)

    # Frame corrente -> lettera
    # Mappatura: il primo frame del range (o dei marker) è 'A'.
    frame_num = scene.frame_current
    all_frames = get_frames_to_render(scene, s.frame_source)
    if frame_num not in all_frames:
        return  # fuori dal range -> niente
    idx = all_frames.index(frame_num)
    letter = frame_letter(idx)
    if letter is None:
        return

    global _live_last_signature

    # Firma: frame + camera attiva + posizioni/rotazioni di target e camere
    sig_parts = [
        str(scene.frame_current),
        str(scene.camera.name if scene.camera else ""),
        str(s.live_quality),
        str(s.live_camera_scope),
    ]
    # Target e camere: posizioni e rotazioni
    for obj in [s.target] + [bpy.data.objects.get(f"SAS_Cam_{i}") for i in range(1, 9)]:
        if obj is None:
            continue
        loc = obj.matrix_world.translation
        rot = obj.matrix_world.to_euler()
        sig_parts.append(f"{obj.name}:{loc.x:.3f},{loc.y:.3f},{loc.z:.3f}")
        sig_parts.append(f"{rot.x:.3f},{rot.y:.3f},{rot.z:.3f}")
    signature = "|".join(sig_parts)

    if signature == _live_last_signature:
        return   # niente da aggiornare
    _live_last_signature = signature

    # Salva lo stato minimo che tocchiamo
    prev_cam = scene.camera
    prev_fmt = scene.render.image_settings.file_format
    prev_mode = scene.render.image_settings.color_mode

    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'

    # Quali angoli?
    if s.sas_compatible and s.death_sprite:
        angles = [0]
    elif s.live_camera_scope == 'ACTIVE':
        cam = scene.camera
        a = _angle_from_camera_name(cam.name) if cam else None
        angles = [a] if a else []
    else:
        angles = list(range(1, 9))

    # HIGH usa il motore di render vero; MEDIUM/LOW usano OpenGL
    use_real_engine = (s.live_quality == 'HIGH')

    # Forza la risoluzione SAS prima del render
    prev_res_x = scene.render.resolution_x
    prev_res_y = scene.render.resolution_y
    prev_pct = scene.render.resolution_percentage
    scene.render.resolution_x = s.res_x
    scene.render.resolution_y = s.res_y
    scene.render.resolution_percentage = 100

    frame_angles = []
    prev_quality_state = _apply_live_quality(
        s.live_quality, use_real_engine, s.live_eevee_samples
    )
    try:
        # Riallinea le camere al target corrente prima di ogni batch di render
        for angle in angles:
            cam_name = "SAS_Cam_1" if angle == 0 else f"SAS_Cam_{angle}"
            cam = bpy.data.objects.get(cam_name)
            if not cam:
                continue
            scene.camera = cam
            filename = f"{sprite_code}{anim_code}{letter}{angle}.png"
            out_path = os.path.join(out_dir, filename)
            if _render_still(out_path, real_engine=use_real_engine):
                frame_angles.append({"angle": angle, "file": filename})
    finally:
        _restore_live_quality(prev_quality_state)
        scene.render.resolution_x = prev_res_x
        scene.render.resolution_y = prev_res_y
        scene.render.resolution_percentage = prev_pct
        scene.camera = prev_cam
        scene.render.image_settings.file_format = prev_fmt
        scene.render.image_settings.color_mode = prev_mode

    if not frame_angles:
        return

    duration_ms = (max(1, int(round(1000.0 / max(1, s.fps))))
                   if s.duration_source == 'FPS'
                   else int(s.default_duration_ms))

    manifest = {
        "version": "1.0",
        "kind": "live",
        "source": "blender_sas_addon",
        "timestamp": datetime.now().isoformat(),
        "sprite":   {"name": s.sprite_name, "code": sprite_code},
        "animation":{"name": s.anim_name,   "code": anim_code,
                     "loop": True, "anchor": "bottom"},
        "output_dir": out_dir,
        "death_sprite": bool(s.death_sprite),
        "frames": [{
            "letter": letter,
            "duration_ms": duration_ms,
            "angles": frame_angles,
        }],
    }
    try:
        write_manifest_atomic(out_dir, manifest)
    except Exception as e:
        print(f"[SAS live] manifest non scritto: {e}")


def _live_tick():
    """Timer ricorrente. Ritorna il prossimo intervallo o None per fermarsi."""
    try:
        s = bpy.context.scene.sas_settings
    except Exception:
        return None
    if not s.live_enabled:
        return None
    try:
        render_live_frame()
    except Exception as e:
        print(f"[SAS live] errore: {e}")
    try:
        return max(0.2, float(s.live_interval))
    except Exception:
        return 1.0

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sas_settings = PointerProperty(type=SAS_Settings)


def unregister():
    del bpy.types.Scene.sas_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()