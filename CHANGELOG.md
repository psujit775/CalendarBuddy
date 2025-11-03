# Changelog

All notable changes to CalendarBuddy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-11-03

### 🎉 Major Release: Enhanced Sync & Improved UX

### Added
- **Lookback Sync**: New `--lookback` argument for historical event syncing
  - `--lookback 0` (default): Today only - fast, efficient for cron jobs
  - `--lookback 7`: Last 7 days - recommended for weekly maintenance
  - `--lookback 30`: Last 30 days - good for initial setup or after vacation
- **Modern CLI**: New `--view` flag replaces `--print-current` (cleaner, more intuitive)
- **Smart Date Parsing**: Support for icalBuddy's "YYYY-MM-DD at HH:MM AM/PM" format
- **Robust Sync Logic**: Improved duplicate event handling with `INSERT OR REPLACE`
- **Lookback Mode**: Prevents marking historical events as "removed" during historical syncs

### Changed
- **CLI Interface**: `--view` is now the primary flag for viewing events
- **Default Behavior**: Explicitly documented as lookback 0 (today only) for performance
- **Sync Performance**: Optimized for different use cases (daily vs maintenance vs initial setup)
- **Documentation**: Complete README overhaul with best practices and automation guides

### Fixed
- **Date Parsing**: Fixed issue where multi-day icalBuddy output defaulted all events to today's date
- **UNIQUE Constraint**: Resolved database conflicts when syncing overlapping date ranges
- **Meeting Link Extraction**: Improved reliability for various calendar formats

### Documentation
- Updated all examples to use `--view` instead of `--print-current`
- Added comprehensive automation recommendations with cron examples
- Clear migration guidelines for existing users

### Backward Compatibility
- `--print-current` still works (hidden but functional)
- Existing scripts continue to work without modification
- Database schema remains compatible

### Migration Guide
- **Recommended**: Update scripts to use `--view` for cleaner syntax
- **Consider**: Adding `--lookback 7` for weekly maintenance syncs
- **Performance**: Keep daily cron jobs at default (lookback 0) for speed

## [1.0.0] - 2025-10-XX

### Added
- Initial release of CalendarBuddy
- Basic calendar sync functionality
- SQLite database storage
- Change tracking and audit log
- Multiple output formats (table, JSON, CSV)
- Meeting link extraction
- Date range filtering
- macOS Calendar.app integration via icalBuddy

---

**Perfect for corporate environments, terminal workflows, and automated calendar management!**