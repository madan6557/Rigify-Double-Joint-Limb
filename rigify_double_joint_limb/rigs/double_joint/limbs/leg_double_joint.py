# SPDX-FileCopyrightText: 2026 MiKy LiRa
# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from mathutils import Matrix, Vector

from rigify.base_rig import stage
from rigify.rigs.limbs.leg import Rig as RigifyLegRig, create_sample as create_leg_sample
from rigify.rigs.limbs.limb_rigs import BaseLimbRig
from rigify.rigs.widgets import create_foot_widget
from rigify.utils.bones import align_bone_orientation, align_bone_x_axis, align_bone_z_axis, align_chain_x_axis, put_bone
from rigify.utils.misc import matrix_from_axis_pair, matrix_from_axis_roll
from rigify.utils.naming import make_derived_name
from rigify.utils.rig import is_rig_base_bone
from rigify.utils.widgets import adjust_widget_transform_mesh

from .double_joint import DoubleJointLimbMixin, register_limb_end_parent


class Rig(DoubleJointLimbMixin, RigifyLegRig):
    """Human leg rig with a generated knee joint."""

    min_valid_orgs = max_valid_orgs = 5

    class MchBones(RigifyLegRig.MchBones):
        ik_mid: str

    bones: RigifyLegRig.ToplevelBones[
        "Rig.OrgBones",
        "Rig.CtrlBones",
        "Rig.MchBones",
        list[str],
    ]

    def find_org_bones(self, bone):
        bones = BaseLimbRig.find_org_bones(self, bone)

        for b in self.get_bone(bones.main[self.end_index]).bone.children:
            if not b.use_connect and not b.children and not is_rig_base_bone(self.obj, b.name):
                bones.heel = b.name
                break
        else:
            self.raise_error("Heel bone not found.")

        return bones

    def prepare_bones(self):
        orgs = self.bones.org.main
        foot = self.get_bone(orgs[self.end_index])
        toe = self.get_bone(orgs[self.end_index + 1])

        ik_y_axis = (0, 1, 0)
        foot_y_axis = -self.vector_without_z(foot.y_axis)
        foot_x = foot_y_axis.cross((0, 0, 1))

        if self.params.rotation_axis == "automatic":
            align_chain_x_axis(self.obj, orgs[0:3])
            align_bone_x_axis(self.obj, foot.name, foot_x)
            align_bone_x_axis(self.obj, toe.name, -foot_x)
            align_bone_x_axis(self.obj, self.bones.org.heel, Vector((0, 0, 1)))

        elif self.params.auto_align_extremity:
            if self.main_axis == "x":
                align_bone_x_axis(self.obj, foot.name, foot_x)
                align_bone_x_axis(self.obj, toe.name, -foot_x)
            else:
                align_bone_z_axis(self.obj, foot.name, foot_x)
                align_bone_z_axis(self.obj, toe.name, -foot_x)

        else:
            ik_y_axis = foot_y_axis

        self.ik_matrix = matrix_from_axis_roll(ik_y_axis, 0)
        self.roll_matrix = matrix_from_axis_pair(ik_y_axis, foot_x, self.main_axis)

    def register_switch_parents(self, pbuilder):
        register_limb_end_parent(self, pbuilder)

    def make_ik_control_bone(self, orgs):
        foot = orgs[self.end_index]
        name = self.copy_bone(foot, make_derived_name(foot, "ctrl", "_ik"))

        if self.pivot_type == "TOE":
            put_bone(self.obj, name, self.get_bone(name).tail, matrix=self.ik_matrix)
        else:
            put_bone(self.obj, name, None, matrix=self.ik_matrix)

        return name

    def make_ik_ctrl_widget(self, ctrl):
        obj = create_foot_widget(self.obj, ctrl)

        if self.pivot_type != "TOE":
            ctrl_bone = self.get_bone(ctrl)
            org = self.get_bone(self.bones.org.main[self.end_index])
            offset = org.tail - (ctrl_bone.custom_shape_transform or ctrl_bone).head
            adjust_widget_transform_mesh(obj, Matrix.Translation(offset))

    @stage.generate_bones
    def make_ik_pivot_controls(self):
        if self.pivot_type == "ANKLE_TOE":
            self.bones.ctrl.ik_spin = self.make_ik_spin_bone(self.bones.org.main)

    def make_ik_spin_bone(self, orgs: list[str]):
        foot = orgs[self.end_index]
        toe = orgs[self.end_index + 1]
        name = self.copy_bone(foot, make_derived_name(foot, "ctrl", "_spin_ik"))
        put_bone(self.obj, name, self.get_bone(toe).head, matrix=self.ik_matrix, scale=0.5)
        return name

    @stage.generate_bones
    def make_heel_control_bone(self):
        foot = self.bones.org.main[self.end_index]
        name = self.copy_bone(foot, make_derived_name(foot, "ctrl", "_heel_ik"))
        put_bone(self.obj, name, None, matrix=self.roll_matrix, scale=0.5)
        self.bones.ctrl.heel = name

    @stage.generate_bones
    def make_ik_toe_control(self):
        if self.use_ik_toe:
            toe = self.bones.org.main[self.end_index + 1]
            self.bones.ctrl.ik_toe = self.make_ik_toe_control_bone(toe)
            self.bones.mch.ik_toe_parent = self.make_ik_toe_parent_mch_bone(toe)

    @stage.parent_bones
    def parent_ik_toe_control(self):
        if self.use_ik_toe:
            mch = self.bones.mch
            align_bone_orientation(self.obj, mch.ik_toe_parent, self.get_mch_heel_toe_output())

            self.set_bone_parent(mch.ik_toe_parent, mch.ik_target, use_connect=True)
            self.set_bone_parent(self.bones.ctrl.ik_toe, mch.ik_toe_parent)

    @stage.configure_bones
    def configure_ik_toe_control(self):
        if self.use_ik_toe:
            self.copy_bone_properties(self.bones.org.main[self.end_index + 1], self.bones.ctrl.ik_toe, props=False)

    @stage.generate_bones
    def make_roll_mch_chain(self):
        orgs = self.bones.org.main
        self.bones.mch.heel = self.make_roll_mch_bones(
            orgs[self.end_index],
            orgs[self.end_index + 1],
            self.bones.org.heel,
        )

    def parent_fk_parent_bone(self, i, parent_mch, prev_ctrl, org, prev_org):
        toe_index = self.end_index + 1

        if i == toe_index:
            if not self.use_ik_toe:
                align_bone_orientation(self.obj, parent_mch, self.get_mch_heel_toe_output())
                self.set_bone_parent(parent_mch, prev_org, use_connect=True)
            else:
                self.set_bone_parent(parent_mch, prev_ctrl, use_connect=True, inherit_scale="ALIGNED")
        else:
            super().parent_fk_parent_bone(i, parent_mch, prev_ctrl, org, prev_org)

    def rig_fk_parent_bone(self, i, parent_mch, org):
        if i == self.end_index + 1:
            if not self.use_ik_toe:
                con = self.make_constraint(parent_mch, "COPY_TRANSFORMS", self.get_mch_heel_toe_output())
                self.make_driver(con, "influence", variables=[(self.prop_bone, "IK_FK")], polynomial=[1.0, -1.0])
        else:
            super().rig_fk_parent_bone(i, parent_mch, org)


def create_sample(obj):
    create_leg_sample(obj)

    bpy.ops.object.mode_set(mode="EDIT")
    arm = obj.data
    ebones = arm.edit_bones

    lower = ebones["shin.L"]
    upper = ebones["thigh.L"]
    joint = ebones.new("knee.L")
    joint.head = lower.head.copy()
    joint.tail = lower.head.lerp(lower.tail, 0.17)
    joint.roll = lower.roll
    joint.parent = upper
    joint.use_connect = True

    lower.use_connect = False
    lower.parent = joint
    lower.head = joint.tail.copy()
    lower.use_connect = True

    # Salin bone collection dari shin ke knee agar sendi terlihat
    # pada layer yang sama di Blender 4.x Bone Collections system
    for collection in lower.collections:
        collection.assign(joint)

    bpy.ops.object.mode_set(mode="OBJECT")
    obj.pose.bones["thigh.L"].rigify_type = "double_joint.limbs.leg_double_joint"

