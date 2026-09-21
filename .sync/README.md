# Patina File Synchronization

This directory contains files that are synchronized to Patina repositories.

> Note: Any files that are not synchronized should not be added in this directory.

## Why Are Files Synchronized?

- To automatically keep all repos up-to-date.
- To ensure consistency of file content across repos with potential for humar error minimized.
- To centralize content for files that need to be local to a repo (e.g. a GitHub action) but contain the same content
  across more than one Patina repo.
- To reduce churn in development repos of files that are not directly related to development.
- To minimize developer time to push file changes across repos.

## When Are Files Synchronized?

- Anytime a file in this directory ([.sync](https://github.com/OpenDevicePartnership/patina-devops/blob/main/.sync/)) is updated
- Anytime the workflow that synchronizes files is updated ([.github/workflows/FileSyncer.yml](https://github.com/OpenDevicePartnership/paina-devops/blob/main/.github/workflows/FileSyncer.yml))
- [Manually](https://github.com/OpenDevicePartnership/patina-devops/actions/workflows/FileSyncer.yml)

The file synchronization workflow is often disabled so files are not synced right away. This leaves it to maintainer
discretion when to manually trigger the synchronization workflow. In some cases, the changes may not have any urgency
and can wait until other changes are accumulated to reduce PR creation thrash and workflow runs in Patina repos. If the
workflow is disabled, enable it, manually run it, and disable it again when done.

## How to Configure File Syncing

All of the file synchronization settings are maintained in the [.sync/Files.yml](https://github.com/OpenDevicePartnership/patina-devops/blob/main/.sync/Files.yml)
configuration file. Refer to the file to see the current synchronization settings and to modify settings.

Any resource versions that might be substituted into files during the sync process are defined in
[.sync/Version.njk](https://github.com/OpenDevicePartnership/patina-devops/blob/main/.sync/Files.yml).
