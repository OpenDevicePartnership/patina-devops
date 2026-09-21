
# Patina DevOps

Patina is a UEFI firmware implementation written in Rust, developed under the
[Open Device Partnership](https://github.com/OpenDevicePartnership) (ODP). The project spans several repositories:
the core firmware and its supporting crates ([patina](https://github.com/OpenDevicePartnership/patina),
[patina-paging](https://github.com/OpenDevicePartnership/patina-paging),
[patina-mtrr](https://github.com/OpenDevicePartnership/patina-mtrr)), QEMU platform integration
([patina-qemu](https://github.com/OpenDevicePartnership/patina-qemu) and
[patina-dxe-core-qemu](https://github.com/OpenDevicePartnership/patina-dxe-core-qemu)), and other supporting repos
with code and tools.

This repository, patina-devops, centralizes the DevOps configuration and automation shared across those
repositories so that common CI/CD behavior, templates, and tooling are maintained in one place instead of being
duplicated in every repo. It provides:

- **Reusable GitHub Actions workflows and composite actions** ([.github/workflows](.github/workflows) and
  [.github/actions](.github/actions)) for CI, release drafting, issue triage, label management, and more. Dependent
  repos call back into these, pinned to a specific commit.
- **Shared configuration templates** ([.sync](.sync)), such as issue/PR templates, Dependabot and markdownlint
  config, and Rust tooling defaults. These are pushed out to dependent repos on a schedule by the
  [Repo File Sync workflow](.github/workflows/FileSyncer.yml), based on the mapping in
  [.sync/Files.yml](.sync/Files.yml).

## Release Process Across Patina Repositories

This section details the process for publishing releases from each Patina repository that does so, including
patina-devops itself.

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

### [patina-devops](https://github.com/OpenDevicePartnership/patina-devops)

A patina-devops release is often made when reusable GitHub workflows (those in `.github/workflows/`) are updated
because they are referenced by version/commit hash from "leaf" workflows used in dependent repositories. They are called
"leaf" workflows because they call the reusable workflows defined in patina-devops. File syncs can happen independently
of releases when files in the `.sync` directory are updated. If the files being synced need to reference a specific
version of patina-devops assets (like reusable workflows), then the file sync process should run after the repo release
process is completed.

Unlike the repos above, patina-devops does not publish to crates.io or attach release binaries. Its release
produces a tagged GitHub release that dependent repos pin to for the shared workflows and actions described at the
top of this document.

- As pull requests are merged to `main`, a [release-drafter](https://github.com/release-drafter/release-drafter)
  workflow (configured with [.github/release-draft-config.yml](.github/release-draft-config.yml)) automatically
  maintains a draft release, computing the next semantic version from the labels applied to each merged PR.

Release steps:

- When it's time to release, publish the draft release from the repository's [Releases page](https://github.com/OpenDevicePartnership/patina-devops/releases).
  This creates the new tag, for example `v0.3.17`.
- Resolve the commit SHA that the new tag points to, for example with `git rev-parse v0.3.17`, or by viewing the
  tag or release page on GitHub.
- Update [.sync/Version.njk](.sync/Version.njk) in a pull request, setting `patina_devops` to the new tag and
  `patina_devops_sha` to the resolved commit SHA.
- Once that PR merges, every synced file that pins to `sync_version.patina_devops_sha`, such as
  [update-release-draft.yml](.sync/workflows/leaf/update-release-draft.yml), picks up the new commit. The
  [Repo File Sync workflow](.github/workflows/FileSyncer.yml) then opens PRs in each dependent repo to update to
  that newly pinned commit.
  - Read the file sync documentation in [.sync/README.md](.sync/README.md) for more details on how the synchronization
    process works and to determine when it is necessary to manually trigger the workflow.
- Merging those PRs is what brings each dependent repo onto the new patina-devops version.

Dependent repos pin to a commit SHA rather than a tag or branch so they are not affected if a tag is ever moved or
deleted. The `patina_devops` tag name is kept alongside the SHA only as a human-readable `# vX.Y.Z` comment.
