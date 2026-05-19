# SPDX-FileCopyrightText: 2026 MiKy LiRa
# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from mathutils import Matrix

from rigify.base_rig import stage
from rigify.rigs.limbs.arm import Rig as RigifyArmRig, create_sample as create_arm_sample
from rigify.rigs.widgets import create_hand_widget
from rigify.utils.bones import compute_chain_x_axis, align_bone_x_axis, align_bone_z_axis, put_bone
from rigify.utils.naming import make_derived_name
from rigify.utils.widgets import adjust_widget_transform_mesh
from rigify.utils.widgets_basic import create_circle_widget

from .double_joint import DoubleJointLimbMixin, register_limb_end_parent


class Rig(DoubleJointLimbMixin, RigifyArmRig):
    """Human arm rig with a generated elbow joint."""

    min_valid_orgs = max_valid_orgs = 4

    class MchBones(RigifyArmRig.MchBones):
        ik_mid: str

    bones: RigifyArmRig.ToplevelBones[
        "Rig.OrgBones",
        "Rig.CtrlBones",
        "Rig.MchBones",
        list[str],
    ]

    def prepare_bones(self):
        orgs = self.bones.org.main

        if self.params.rotation_axis == "automatic":
            axis = compute_chain_x_axis(self.obj, orgs[0:3])

            for bone in orgs:
                align_bone_x_axis(self.obj, bone, axis)

        elif self.params.auto_align_extremity:
            axis = self.vector_without_z(self.get_bone(orgs[self.end_index]).z_axis)

            align_bone_z_axis(self.obj, orgs[self.end_index], axis)

    def register_switch_parents(self, pbuilder):
        register_limb_end_parent(self, pbuilder)

    def make_ik_ctrl_widget(self, ctrl):
        create_hand_widget(self.obj, ctrl)

    @stage.generate_bones
    def make_wrist_pivot_control(self):
        if self.make_wrist_pivot:
            org = self.bones.org.main[self.end_index]
            self.bones.ctrl.ik_wrist = self.make_wrist_pivot_bone(org)
            self.bones.mch.ik_wrist = self.copy_bone(org, make_derived_name(org, "mch", "_ik_wrist"), scale=0.25)

    def make_wrist_pivot_bone(self, org):
        name = self.copy_bone(org, make_derived_name(org, "ctrl", "_ik_wrist"), scale=0.5)
        put_bone(self.obj, name, self.get_bone(org).tail)
        return name

    @stage.generate_widgets
    def make_wrist_pivot_widget(self):
        if self.make_wrist_pivot:
            ctrl = self.bones.ctrl.ik_wrist

            if self.main_axis == "x":
                obj = create_circle_widget(self.obj, ctrl, head_tail=-0.3, head_tail_x=0.5)
            else:
                obj = create_circle_widget(self.obj, ctrl, head_tail=0.5, head_tail_x=-0.3)

            if obj:
                org_bone = self.get_bone(self.bones.org.main[self.end_index])
                offset = org_bone.head - self.get_bone(ctrl).head
                adjust_widget_transform_mesh(obj, Matrix.Translation(offset))


def create_sample(obj):
    create_arm_sample(obj)

    bpy.ops.object.mode_set(mode="EDIT")
    arm = obj.data
    ebones = arm.edit_bones

    lower = ebones["forearm.L"]
    upper = ebones["upper_arm.L"]
    joint = ebones.new("elbow.L")
    joint.head = lower.head.copy()
    joint.tail = lower.head.lerp(lower.tail, 0.15)
    joint.roll = lower.roll
    joint.parent = upper
    joint.use_connect = True

    lower.use_connect = False
    lower.parent = joint
    lower.head = joint.tail.copy()
    lower.use_connect = True

    bpy.ops.object.mode_set(mode="OBJECT")
    obj.pose.bones["upper_arm.L"].rigify_type = "double_joint.limbs.arm_double_joint"
