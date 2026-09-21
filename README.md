
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
