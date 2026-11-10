# Changelog

All notable changes to Celvo are documented here.

---

## v1.3.0 (unreleased)

### Added

- Platform-specific Windows WASAPI and Linux PulseAudio audio backends
- Synchronized, bounded-memory recording and chunked WAV mixing
- Cross-platform CLI, paths, Whisper discovery, and Windows installer
- Hardware-free test suite and Windows/Linux CI

### Improved

- Recording errors are propagated and failed captures are preserved as partials
- Whisper failures and missing outputs are reported instead of treated as success

## v1.2.2

### Improved

- Cleaner README
- Added project badges
- Added Ubuntu minimal installation notes
- Added validated installation screenshots
- Improved installer reliability
- Improved dependency detection
- Improved documentation
- General project cleanup

---

## v1.2.1

### Added

- Clean installation support for Fedora
- Clean installation support for Ubuntu
- Automatic dependency installation
- `record` and `process` global commands

---

## v1.0.0

Initial release.
