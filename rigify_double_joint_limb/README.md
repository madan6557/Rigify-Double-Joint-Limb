# Rigify Double Joint Limb

Rigify Double Joint Limb is an external Rigify feature set for Blender 4.3.2. It duplicates a Rigify human metarig, inserts extra elbow and knee joint bones, and lets Rigify generate a rig that already contains the required FK, IK, tweak, MCH, ORG, and DEF retargeting.

This add-on does not modify Blender's built-in Rigify files.

## What It Solves

Default Rigify human limbs use a single bend joint for the elbow and knee. For some character styles, that bend can look too sharp or unnatural. This feature set converts the metarig before generation so the generated rig has an extra short joint segment:

- Arm: `upper_arm -> elbow -> forearm -> hand`
- Leg: `thigh -> knee -> shin -> foot -> toe`

The goal is to avoid editing the generated Rigify rig manually, especially the repetitive retargeting work across ORG, FK, IK, MCH, tweak, and DEF bones.

## Requirements

- Blender 4.3.2
- Built-in Rigify add-on enabled
- Rigify human metarig, left and right sides using standard human metarig names

Supported sides in v1:

- `.L`
- `.R`

## Install

1. Open Blender.
2. Go to `Edit > Preferences > Add-ons`.
3. Enable the built-in `Rigify` add-on.
4. Open the Rigify add-on preferences.
5. Click `Install Feature Set from File`.
6. Select `rigify_double_joint_limb.zip`.
7. Enable `Rigify Double Joint Limb` in the Rigify feature set list.

If the feature set is not visible, restart Blender and check the Rigify preferences again.

## Basic Workflow

1. Add or select a Rigify human metarig.
2. Make sure you are selecting the metarig, not a generated Rigify rig.
3. Run `Object > Duplicate Double Joint Metarig`.
4. Adjust the operator options if needed:
   - `Elbow Joint Length`
   - `Knee Joint Length`
5. Select the duplicated metarig.
6. Use the normal Rigify `Generate Rig` button.

The original metarig is kept unchanged. The add-on creates a duplicate named like:

```text
metarig_double_joint
```

## Generated Bone Behavior

The generated rig includes the added elbow and knee bones across the Rigify layers that need them.

Expected important bones include:

```text
ORG-elbow.L
ORG-elbow.R
ORG-knee.L
ORG-knee.R
elbow_fk.L
elbow_fk.R
knee_fk.L
knee_fk.R
MCH-elbow_ik.L
MCH-elbow_ik.R
MCH-knee_ik.L
MCH-knee_ik.R
elbow_tweak.L
elbow_tweak.R
knee_tweak.L
knee_tweak.R
DEF-elbow.L
DEF-elbow.R
DEF-knee.L
DEF-knee.R
```

## Constraint Retargeting

The add-on retargets the generated Rigify chains so manual constraint editing is not needed.

Main behavior:

- ORG elbow and knee bones copy from the added FK and IK/MCH joint controls.
- Lower limb ORG bones follow the lower FK and lower IK/MCH chain through the added joint.
- IK chain count is `3` for arms and legs.
- FK parenting includes the new joint:
  - `forearm_fk` parented under `elbow_fk`
  - `shin_fk` parented under `knee_fk`
- DEF stretch targets are rebuilt around the added joint and tweak bones.
- Constraint targets use generated rig bone names from this feature set, not stale targets from the default Rigify limb chain.

## Rig Types

This feature set adds these Rigify rig types:

```text
double_joint.limbs.arm_double_joint
double_joint.limbs.leg_double_joint
```

The converter automatically assigns these types to:

```text
upper_arm.L
upper_arm.R
thigh.L
thigh.R
```

The inserted child bones clear their own `rigify_type`, because the parent chain rig type owns the full limb generation.

## Troubleshooting

### The operator says no supported chains were found

Check that you selected a Rigify human metarig with standard bone names:

```text
upper_arm.L
forearm.L
hand.L
thigh.L
shin.L
foot.L
toe.L
```

The same names must exist for `.R`.

### I selected the generated rig by mistake

Select the metarig instead. The operator intentionally rejects generated rigs.

### Generate Rig does not show the custom rig types

Confirm that:

- Rigify is enabled.
- The feature set is installed from `rigify_double_joint_limb.zip`.
- `Rigify Double Joint Limb` is enabled in Rigify preferences.
- Blender was restarted after installation if the feature set did not appear immediately.

### The bend shape still needs adjustment

Use the generated tweak controls:

```text
elbow_tweak.L
elbow_tweak.R
knee_tweak.L
knee_tweak.R
```

The add-on creates the double joint rig structure, but final deformation quality still depends on mesh topology and weight painting.

## Development Layout

```text
rigify_double_joint_limb/
  __init__.py
  rigs/
    __init__.py
    double_joint/
      __init__.py
      limbs/
        __init__.py
        arm_double_joint.py
        double_joint.py
        leg_double_joint.py
```

## Validation Checklist

Tested target:

- Blender 4.3.2
- Rigify human metarig

Recommended checks after changes:

1. Install the feature set from zip.
2. Add a Rigify human metarig.
3. Run `Duplicate Double Joint Metarig`.
4. Generate the rig from the duplicated metarig.
5. Confirm these bones exist:
   - `ORG-elbow.L`
   - `ORG-knee.L`
   - `elbow_fk.L`
   - `knee_fk.L`
   - `MCH-elbow_ik.L`
   - `MCH-knee_ik.L`
   - `elbow_tweak.L`
   - `knee_tweak.L`
   - `DEF-elbow.L`
   - `DEF-knee.L`
6. Confirm arm and leg IK constraints use chain count `3`.
7. Pose test with IK and FK on elbows and knees.
8. Check tweak controls for deformation correction.

## Limitations

- v1 targets the standard Rigify human metarig only.
- v1 supports `.L` and `.R` side names only.
- The add-on does not fix mesh topology or weight painting.
- The add-on does not edit Blender's built-in Rigify installation.

## License

Copyright (C) 2026 MiKy LiRa.

This project is licensed under `GPL-3.0-or-later`. See [LICENSE](LICENSE).
