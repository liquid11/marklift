# Changelog

Notable changes to Marklift are documented here.

## 1.0.1 - 2026-07-24

### Fixed

- Restored the Marklift application icon in packaged Windows builds by resolving
  bundled assets from the installed package instead of the PyInstaller entry
  script location.
- Added consistent, high-contrast icons to the file, folder, copy, save, batch
  save, and cancel actions.
- Included PNG, ICO, and SVG interface assets in both Python packages and
  packaged application builds.

### Quality

- Added UI coverage that verifies the application icon and every action icon can
  be loaded from packaged resources.
- Made the UI test completion gate wait for the worker thread itself, preventing
  a Qt shutdown race between sequential conversion tests.
- Refreshed the main-window screenshot to show the corrected Windows interface.
