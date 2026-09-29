# SPDX-FileCopyrightText: 2026 MiKy LiRa
# SPDX-License-Identifier: GPL-3.0-or-later

rigify_info = {
    "name": "Rigify Double Joint Limb",
    "author": "MiKy LiRa",
    "description": "Rigify feature set for human arm and leg double joint generation.",
    "link": "https://local/rigify-double-joint-limb",
    "license": "GPL-3.0-or-later",
}

import bpy


FEATURE_SET_ID = "rigify_double_joint_limb"
ARM_RIG_TYPE = "double_joint.limbs.arm_double_joint"
LEG_RIG_TYPE = "double_joint.limbs.leg_double_joint"


class RIGIFY_DOUBLE_JOINT_OT_duplicate_metarig(bpy.types.Operator):
    bl_idname = "rigify_double_joint.duplicate_metarig"
    bl_label = "Duplicate Double Joint Metarig"
    bl_description = "Duplicate a Rigify human metarig and convert arms and legs to double joint limbs"
    bl_options = {"REGISTER", "UNDO"}

    arm_joint_ratio: bpy.props.FloatProperty(
        name="Elbow Joint Length",
        description="Portion of the original forearm reserved for the extra elbow joint bone",
        default=0.15,
        min=0.02,
        max=0.45,
        subtype="FACTOR",
    )

    leg_joint_ratio: bpy.props.FloatProperty(
        name="Knee Joint Length",
        description="Portion of the original shin reserved for the extra knee joint bone",
        default=0.17,
        min=0.02,
        max=0.45,
        subtype="FACTOR",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "ARMATURE" and obj.mode in {"OBJECT", "POSE"}

    def execute(self, context):
        source = context.object

        if source.data.get("rig_id"):
            self.report({"ERROR"}, "Select the metarig, not a generated rig.")
            return {"CANCELLED"}

        duplicate = self._duplicate_armature(context, source)

        try:
            self._convert_metarig(context, duplicate)
        except Exception as exc:
            # Bersihkan objek duplikat agar tidak tersisa sebagai orphan di scene
            if context.object and context.object.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.data.objects.remove(duplicate, do_unlink=True)
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        finally:
            if context.object and context.object.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

        context.view_layer.objects.active = duplicate
        duplicate.select_set(True)
        source.select_set(False)

        self.report({"INFO"}, "Created double joint metarig.")
        return {"FINISHED"}

    def _duplicate_armature(self, context, source):
        duplicate = source.copy()
        duplicate.data = source.data.copy()
        duplicate.animation_data_clear()
        duplicate.name = self._unique_name(source.name + "_double_joint")
        duplicate.data.name = self._unique_name(source.data.name + "_double_joint")

        # Hapus referensi ke rig hasil generate milik metarig sumber.
        # Tanpa ini, Rigify akan menimpa rig lama pengguna saat Generate Rig dipanggil
        # pada metarig duplikat ini.
        if hasattr(duplicate.data, "rigify_target_rig"):
            duplicate.data.rigify_target_rig = None
        duplicate.data.pop("rigify_target_rig", None)

        collection = source.users_collection[0] if source.users_collection else context.collection
        collection.objects.link(duplicate)

        for obj in context.selected_objects:
            obj.select_set(False)

        duplicate.select_set(True)
        context.view_layer.objects.active = duplicate

        return duplicate

    def _convert_metarig(self, context, obj):
        bpy.ops.object.mode_set(mode="EDIT")

        converted = 0
        converted += self._convert_side(obj, "L")
        converted += self._convert_side(obj, "R")

        bpy.ops.object.mode_set(mode="OBJECT")

        if converted == 0:
            raise RuntimeError("No supported Rigify human arm or leg chains were found.")

        if hasattr(obj.data, "active_feature_set"):
            try:
                obj.data.active_feature_set = FEATURE_SET_ID
            except (TypeError, ValueError):
                pass

        self._assign_rig_types(obj, "L")
        self._assign_rig_types(obj, "R")



    def _convert_side(self, obj, side):
        arm = obj.data
        ebones = arm.edit_bones
        suffix = "." + side
        converted = 0

        if self._has_chain(ebones, ["upper_arm", "forearm", "hand"], suffix):
            if self._insert_joint(arm, "upper_arm" + suffix, "forearm" + suffix, "elbow" + suffix, self.arm_joint_ratio):
                converted += 1

        if self._has_chain(ebones, ["thigh", "shin", "foot", "toe"], suffix):
            if self._insert_joint(arm, "thigh" + suffix, "shin" + suffix, "knee" + suffix, self.leg_joint_ratio):
                converted += 1

        return converted

    @staticmethod
    def _has_chain(ebones, names, suffix):
        return all((name + suffix) in ebones for name in names)

    def _insert_joint(self, arm, upper_name, lower_name, joint_name, ratio):
        ebones = arm.edit_bones

        if joint_name in ebones:
            return False

        upper = ebones[upper_name]
        lower = ebones[lower_name]

        joint_head = lower.head.copy()
        joint_tail = lower.head.lerp(lower.tail, ratio)

        joint = ebones.new(joint_name)
        joint.head = joint_head
        joint.tail = joint_tail
        joint.roll = lower.roll
        joint.parent = upper
        joint.use_connect = True
        joint.inherit_scale = lower.inherit_scale

        lower.use_connect = False
        lower.parent = joint
        lower.head = joint.tail.copy()
        lower.use_connect = True

        self._copy_bone_collections(lower, joint)

        return True

    @staticmethod
    def _copy_bone_collections(source, target):
        for collection in source.collections:
            collection.assign(target)

    def _assign_rig_types(self, obj, side):
        suffix = "." + side

        # Hanya pasang rig type jika bone sendi benar-benar ada.
        # Jika _insert_joint gagal (misalnya karena chain tidak lengkap, toe tidak ada,
        # dsb.), kita tidak ingin memaksa rig type yang akan menyebabkan error saat Generate.
        if ("elbow" + suffix) in obj.data.bones:
            self._assign_limb_type(obj, "upper_arm" + suffix, ARM_RIG_TYPE)

        if ("knee" + suffix) in obj.data.bones:
            self._assign_limb_type(obj, "thigh" + suffix, LEG_RIG_TYPE)

        for name in ("elbow", "forearm", "hand", "knee", "shin", "foot", "toe"):
            pbone = obj.pose.bones.get(name + suffix)
            if pbone:
                pbone.rigify_type = ""


    @staticmethod
    def _assign_limb_type(obj, bone_name, rig_type):
        pbone = obj.pose.bones.get(bone_name)
        if not pbone:
            return

        saved = {}
        params = pbone.rigify_parameters
        for attr in (
            "rotation_axis",
            "auto_align_extremity",
            "segments",
            "bbones",
            "make_custom_pivot",
            "ik_local_location",
            "limb_uniform_scale",
            "make_ik_wrist_pivot",
            "foot_pivot_type",
            "extra_ik_toe",
            "extra_toe_roll",
        ):
            if hasattr(params, attr):
                saved[attr] = getattr(params, attr)

        pbone.rigify_type = rig_type

        params = pbone.rigify_parameters
        for attr, value in saved.items():
            if hasattr(params, attr):
                setattr(params, attr, value)

    @staticmethod
    def _unique_name(base):
        existing = set(bpy.data.objects.keys()) | set(bpy.data.armatures.keys())
        if base not in existing:
            return base

        index = 1
        while True:
            name = "{}.{:03d}".format(base, index)
            if name not in existing:
                return name
            index += 1


def _menu_func(self, _context):
    self.layout.operator(RIGIFY_DOUBLE_JOINT_OT_duplicate_metarig.bl_idname, icon="DUPLICATE")


classes = (RIGIFY_DOUBLE_JOINT_OT_duplicate_metarig,)


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError as exc:
            if "already registered" not in str(exc):
                raise

    try:
        bpy.types.VIEW3D_MT_object.remove(_menu_func)
    except (AttributeError, ValueError):
        pass
    bpy.types.VIEW3D_MT_object.append(_menu_func)


def unregister():
    try:
        bpy.types.VIEW3D_MT_object.remove(_menu_func)
    except (AttributeError, ValueError):
        pass

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError as exc:
            if "missing bl_rna" not in str(exc):
                raise
