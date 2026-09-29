# SPDX-FileCopyrightText: 2026 MiKy LiRa
# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
from itertools import count

from rigify.base_generate import BaseGenerator
from rigify.base_rig import stage
from rigify.rigs.limbs.limb_rigs import BaseLimbRig, SegmentEntry
from rigify.utils.bones import put_bone
from rigify.utils.misc import map_list, padnone
from rigify.utils.naming import make_derived_name
from rigify.utils.widgets import GeometryData
from rigify.utils.widgets_basic import create_circle_widget, create_limb_widget


class DoubleJointLimbMixin:
    joint_index = 1
    lower_index = 2
    end_index = 3
    ik_chain_count = 3

    def initialize(self):
        super().initialize()

        self.fk_name_suffix_cutoff = self.end_index
        self.fk_ik_layer_cutoff = self.end_index + 1
        self._build_double_joint_segment_tables()

    @stage.generate_bones
    def generate_bones(self):
        orgs = self.bones.org.main
        # Gunakan bone upper dan lower (bukan intermediate joint) untuk menghitung arah siku/lutut dan pole angle
        bones = [self.get_bone(orgs[0]), self.get_bone(orgs[self.lower_index])]

        self.elbow_vector = self.compute_elbow_vector(bones)
        self.pole_angle = self.compute_pole_angle(bones, self.elbow_vector)
        self.rig_parent_bone = self.get_bone_parent(orgs[0])

    def _build_double_joint_segment_tables(self):
        orgs = self.bones.org.main
        upper = orgs[0]
        joint = orgs[self.joint_index]
        lower = orgs[self.lower_index]

        self.segment_table = [
            *[
                SegmentEntry(upper, 0, seg, self.get_segment_pos(upper, seg))
                for seg in range(self.segments)
            ],
            SegmentEntry(joint, self.joint_index, None, self.get_bone(joint).head),
            *[
                SegmentEntry(lower, self.lower_index, seg, self.get_segment_pos(lower, seg))
                for seg in range(self.segments)
            ],
        ]

        self.segment_table_end = [
            SegmentEntry(org, index, None, self.get_bone(org).head)
            for index, org in enumerate(orgs[self.end_index:], start=self.end_index)
        ]

        self.segment_table_full = self.segment_table + self.segment_table_end
        self.segment_table_tweak = self.segment_table + self.segment_table_end[0:1]

    def make_fk_parent_bone(self, i: int, org: str):
        if i >= self.end_index:
            return self.copy_bone(org, self.get_fk_name(i, org, "mch"), parent=True, scale=1 / 4)

    def parent_fk_parent_bone(self, i: int, parent_mch: str | None,
                              prev_ctrl: str, _org: str, _prev_org: str | None):
        if i >= self.end_index and parent_mch:
            self.set_bone_parent(parent_mch, prev_ctrl, use_connect=True, inherit_scale="NONE")

    def rig_fk_parent_bone(self, i: int, parent_mch: str | None, _org: str):
        if i >= self.end_index and parent_mch:
            self.make_constraint(parent_mch, "COPY_SCALE", self.bones.mch.follow, use_make_uniform=True)

    def configure_fk_control_bone(self, i: int, ctrl: str, org: str):
        self.copy_bone_properties(org, ctrl)

        # Bone FK selain root hanya boleh berotasi; kunci translasi lokal agar animator
        # tidak menggeser bone ini secara tidak sengaja (G key di Pose Mode).
        if i > 0:
            self.get_bone(ctrl).lock_location = True, True, True

    def make_fk_control_widget(self, i: int, ctrl: str):
        if i < self.end_index:
            obj = create_limb_widget(self.obj, ctrl)
            func = create_limb_widget.__wrapped__
            kwargs = {}
        elif i == self.end_index:
            obj = create_circle_widget(self.obj, ctrl, radius=0.4, head_tail=0.0)
            func = create_circle_widget.__wrapped__
            kwargs = {"radius": 0.4, "head_tail": 0.0}
        else:
            obj = create_circle_widget(self.obj, ctrl, radius=0.4, head_tail=0.5)
            func = create_circle_widget.__wrapped__
            kwargs = {"radius": 0.4, "head_tail": 0.5}

        # Rigify mempertahankan objek widget lama jika sudah ada di scene saat re-generate,
        # sehingga mesh lama (misal circle lama di pergelangan/telapak) tidak otomatis diperbarui.
        # Jika obj is None, kita paksa perbarui data mesh-nya dengan geometri yang benar.
        if obj is None:
            generator = BaseGenerator.instance
            wgt_obj = None
            if generator:
                wgt_obj = generator.new_widget_table.get(ctrl)
            if not wgt_obj:
                wgt_name = f"WGT-{self.obj.name}_{ctrl}"
                wgt_obj = bpy.context.scene.objects.get(wgt_name)

            if wgt_obj and hasattr(wgt_obj, "data") and wgt_obj.data:
                geom = GeometryData()
                func(geom, **kwargs)
                mesh = wgt_obj.data
                mesh.clear_geometry()
                mesh.from_pydata(geom.verts, geom.edges, geom.faces)
                mesh.update()


    def make_ik_control_bone(self, orgs: list[str]):
        org = orgs[self.end_index]
        return self.copy_bone(org, make_derived_name(org, "ctrl", "_ik"))

    def make_ik_scale_bone(self, ctrl: str, orgs: list[str]):
        org = orgs[self.end_index]
        return self.copy_bone(ctrl, make_derived_name(org, "mch", "_ik_scale"), scale=1 / 2)

    def get_ik_output_chain(self):
        return [
            self.get_ik_chain_base(),
            self.bones.mch.ik_mid,
            self.bones.mch.ik_end,
            self.bones.mch.ik_target,
        ]

    def make_ik_mch_chain(self):
        orgs = self.bones.org.main

        if self.use_mch_ik_base:
            self.bones.mch.ik_base = self.make_ik_mch_base_bone(orgs)

        self.bones.mch.ik_swing = self.make_ik_mch_swing_bone(orgs)
        self.bones.mch.ik_target = self.make_ik_mch_target_bone(orgs)
        self.bones.mch.ik_mid = self.copy_bone(
            orgs[self.joint_index],
            make_derived_name(orgs[self.joint_index], "mch", "_ik"),
        )
        self.bones.mch.ik_end = self.copy_bone(
            orgs[self.lower_index],
            make_derived_name(orgs[self.lower_index], "mch", "_ik"),
        )

    def make_ik_mch_swing_bone(self, orgs):
        name = self.copy_bone(orgs[0], make_derived_name(orgs[0], "mch", "_ik_swing"))
        bone = self.get_bone(name)
        bone.tail = bone.head + (self.get_bone(orgs[self.end_index]).head - bone.head).normalized() * bone.length * 0.3
        return name

    def make_ik_mch_target_bone(self, orgs):
        return self.copy_bone(orgs[self.end_index], make_derived_name(orgs[0], "mch", "_ik_target"))

    def parent_ik_mch_chain(self):
        mch = self.bones.mch

        if self.use_mch_ik_base:
            self.set_bone_parent(mch.ik_swing, self.bones.ctrl.ik_base, inherit_scale="AVERAGE")
            self.set_bone_parent(mch.ik_base, mch.ik_swing)
        else:
            self.set_bone_parent(mch.ik_swing, mch.follow)

        self.set_bone_parent(mch.ik_target, self.get_ik_input_bone())
        self.set_bone_parent(mch.ik_mid, self.get_ik_chain_base())
        self.set_bone_parent(mch.ik_end, mch.ik_mid, use_connect=True)

    def configure_ik_mch_chain(self):
        for bone_name in (self.get_ik_chain_base(), self.bones.mch.ik_end):
            self.get_bone(bone_name).ik_stretch = 0.1

        self.get_bone(self.bones.mch.ik_mid).ik_stretch = 0.0

        for bone_name in (self.bones.mch.ik_mid, self.bones.mch.ik_end):
            bone = self.get_bone(bone_name)
            bone.lock_ik_x = bone.lock_ik_y = bone.lock_ik_z = True
            setattr(bone, "lock_ik_" + self.main_axis, False)

    def rig_ik_mch_chain(self):
        mch = self.bones.mch
        input_bone = self.get_ik_input_bone()

        self.make_constraint(mch.ik_swing, "DAMPED_TRACK", mch.ik_target)
        self.rig_ik_mch_stretch_limit(
            mch.ik_target,
            mch.follow,
            input_bone,
            self.ik_input_head_tail,
            self.ik_chain_count,
            bias=1.0,
        )
        self.rig_ik_mch_end_bone(
            mch.ik_end,
            mch.ik_target,
            self.bones.ctrl.ik_pole,
            chain=self.ik_chain_count,
        )

    def rig_tweak_mch_bone(self, i: int, tweak: str, entry: SegmentEntry):
        if entry.seg_idx:
            prev_tweak, next_tweak, fac = self.get_tweak_blend(i, entry)

            self.make_constraint(tweak, "COPY_TRANSFORMS", prev_tweak)
            self.make_constraint(tweak, "COPY_TRANSFORMS", next_tweak, influence=fac)
            self.make_constraint(tweak, "DAMPED_TRACK", next_tweak)
        else:
            self.make_constraint(tweak, "COPY_SCALE", self.bones.mch.follow, use_make_uniform=True)

        if i == 0:
            self.make_constraint(tweak, "COPY_LOCATION", entry.org)
            self.make_constraint(tweak, "DAMPED_TRACK", entry.org, head_tail=1)

    def parent_org_chain(self):
        orgs = self.bones.org.main
        first_tail_index = self.end_index + 1

        if len(orgs) > first_tail_index:
            self.get_bone(orgs[first_tail_index]).use_connect = False

    def rig_org_chain(self):
        ik = self.get_ik_output_chain() + self.get_tail_ik_controls()

        for args in zip(count(0), self.bones.org.main, self.bones.ctrl.fk, padnone(ik)):
            self.rig_org_bone(*args)

    def make_tweak_chain(self):
        self.bones.ctrl.tweak = map_list(self.make_tweak_bone, count(0), self.segment_table_tweak)

    def make_tweak_mch_chain(self):
        self.bones.mch.tweak = map_list(self.make_tweak_mch_bone, count(0), self.segment_table_tweak)

    def make_deform_chain(self):
        self.bones.deform = map_list(self.make_deform_bone, count(0), self.segment_table_full)


def register_limb_end_parent(rig, pbuilder):
    BaseLimbRig.register_switch_parents(rig, pbuilder)
    pbuilder.register_parent(
        rig,
        rig.bones.org.main[rig.end_index],
        exclude_self=True,
        tags={"limb_end"},
    )
