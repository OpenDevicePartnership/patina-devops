
# Patina

This repository manages devops related content for Patina repositories.

## Patina Repository Release Process

This section details the process for publishing releases from each Patina repo that does so.

### [patina](https://github.com/OpenDevicePartnership/patina)

The patina repo is published by running a
[GitHub Action](https://github.com/OpenDevicePartnership/patina/actions/workflows/crate-version-update.yml) manually.
This creates a new PR in the repo bumping all of the crate versions in lockstep.

Once this PR is approved and merged, it will kick off another workflow automatically that publishes a GitHub release
with the new version. At this point, the release is complete and viewable on GitHub and the crates are published to
crates.io.

If changes need to be made while the version update PR is active, that PR should be closed and regenerated through
the workflow after any other PRs are merged. This ensures that the crate versions updated to match what the GitHub
release will be.

### [patina-paging](https://github.com/OpenDevicePartnership/patina-paging)

The patina-paging repo is published by running a
[GitHub Action](https://github.com/OpenDevicePartnership/patina-paging/actions/workflows/crate-version-update.yml)
manually. This creates a new PR in the repo bumping all of the crate versions in lockstep.

Once this PR is approved and merged, it will kick off another workflow automatically that publishes a GitHub release
with the new version. At this point, the release is complete and viewable on GitHub and the crates are published to
crates.io.

If changes need to be made while the version update PR is active, that PR should be closed and regenerated through
the workflow after any other PRs are merged. This ensures that the crate versions updated to match what the GitHub
release will be.

### [patina-mtrr](https://github.com/OpenDevicePartnership/patina-mtrr)

The patina-mtrr repo is published by running a
[GitHub Action](https://github.com/OpenDevicePartnership/patina-mtrr/actions/workflows/crate-version-update.yml)
manually. This creates a new PR in the repo bumping all of the crate versions in lockstep.

Once this PR is approved and merged, it will kick off another workflow automatically that publishes a GitHub release
with the new version. At this point, the release is complete and viewable on GitHub and the crates are published to
crates.io.

If changes need to be made while the version update PR is active, that PR should be closed and regenerated through
the workflow after any other PRs are merged. This ensures that the crate versions updated to match what the GitHub
release will be.

### [patina-dxe-core-qemu](https://github.com/OpenDevicePartnership/patina-dxe-core-qemu)

The patina-dxe-core-qemu repo release process begins by updating the version in Cargo.toml to reflect the version in
the GitHub release draft. That version should have been updated to an accurate semantic version by the correct GitHub
labels being applied to earlier pull requests. If it is not correct for some reason, then the release draft and the
Cargo.toml version can be manually updated.

Once the Cargo.toml version is correctly set, the release is made by publishing a pending GitHub release in the
repository. This triggers the [GitHub release workflow](https://github.com/OpenDevicePartnership/patina-dxe-core-qemu/blob/main/.github/workflows/publish-binaries.yml),
which will build all patina-dxe-core-qemu binary variants and attach those onto the published GitHub release.

The binaries are attached as an asset to the release in a single zip file.

### [patina-qemu](https://github.com/OpenDevicePartnership/patina-qemu)

The patina-qemu repo release is made by publishing a pending GitHub release in the repository. This triggers the
[GitHub release workflow](https://github.com/OpenDevicePartnership/patina-qemu/blob/main/.github/workflows/platform-ci.yml),
which is the standard CI workflow with special logic for a release trigger.

The patina-qemu repo follows a "dual release" process, meaning it publishes HAF/TF-A binaries ("Release 1") and then pulls
those back into the platform firmware build (for "Release 2").

The high-level release process is:

- If HAF/TF-A binaries need to be updated:
  - Sets `HAF_TFA_EXTDEP_BINS_CURRENT` to `False` in [Platforms/QemuArmVirtPkg/PlatformBuild.py](https://github.com/OpenDevicePartnership/patina-qemu/blob/47f5b014e0b4aab2e5f596524594d41bb17e24bd/Platforms/QemuArmVirtPkg/PlatformBuild.py#L34-L38)
  - Merge the PR
  - Perform a GitHub release that becomes "Release 1"
    - Note that during this time the published HAF/TF-A binaries are not being used and always will be built locally.
      Since HAF/TF-A cannot build on a Windows host, this means the Windows ArmVirt builds will fail as they cannot
      produce the platform firmware binaries that depend on the HAF/TF-A binaries.
- Now that the HAF/TF-A binaries have been published, update [Platforms/QemuArmVirtPkg/Binaries/haf_tfa_binaries_ext_dep.yaml](https://github.com/OpenDevicePartnership/patina-qemu/blob/47f5b014e0b4aab2e5f596524594d41bb17e24bd/Platforms/QemuArmVirtPkg/Binaries/haf_tfa_binaries_ext_dep.yaml)
  to pick up the newly published HAF/TF-A binaries.
  - Set `HAF_TFA_EXTDEP_BINS_CURRENT` to `True` in [Platforms/QemuArmVirtPkg/PlatformBuild.py](https://github.com/OpenDevicePartnership/patina-qemu/blob/47f5b014e0b4aab2e5f596524594d41bb17e24bd/Platforms/QemuArmVirtPkg/PlatformBuild.py#L34-L38)
  - Merge the PR
  - Perform a GitHub release for "Release 2"
    - A correct "Release 2" should have a total of six attached assets:
      1. Source code (zip)
      2. Source code (tar.gz)
      3. HAF/TF-A binaries (zip)
      4. HAF/TF-A binaries (tar.gz)
      5. ArmVirt platform firmware binaries (zip)
      6. Q35 platform firmware binaries (zip)

"Release 1" is an intermediate release and "Release 2" should be made immediately after as part of the overall release
process.
