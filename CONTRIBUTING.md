# Contributing to CalendarBuddy

Thank you for your interest in contributing to CalendarBuddy! This guide will help you get started.

## 🤝 Ways to Contribute

- **Bug Reports**: Found a parsing issue or unexpected behavior?
- **Feature Requests**: Ideas for new functionality or integrations?
- **Code Contributions**: Bug fixes, new features, or improvements
- **Documentation**: Improvements to README, examples, or inline docs
- **Testing**: Help test on different macOS versions or calendar setups

## 🐛 Reporting Bugs

When reporting bugs, please include:

1. **CalendarBuddy version**: `./calendarbuddy.py --version`
2. **macOS version**: `sw_vers`
3. **icalBuddy version**: `icalBuddy --version`
4. **Sample icalBuddy output** (if parsing issue):
   ```bash
   icalBuddy -nrd -df "%Y-%m-%d" -tf "%I:%M %p" eventsToday > sample_output.txt
   ```
5. **Expected vs actual behavior**
6. **Error messages or logs**

### Privacy Note
When sharing calendar output, please **sanitize personal information** like:
- Meeting titles
- Attendee names/emails  
- Meeting URLs
- Location details

## 💡 Feature Requests

Great feature ideas include:
- **Calendar filtering**: Support for specific calendars only
- **Time zone handling**: Better TZ support for remote teams
- **Export formats**: Additional output options
- **Integration examples**: New automation scripts
- **Performance**: Optimizations for large calendar datasets

Please check existing issues before submitting new requests.

## 🛠️ Development Setup

### Prerequisites
- macOS 10.14+
- Python 3.6+
- icalBuddy installed
- Calendar app with test events

### Local Development
```bash
# Fork and clone your fork
git clone https://github.com/yourusername/CalendarBuddy.git
cd CalendarBuddy

# Create a development copy
cp calendarbuddy.py calendarbuddy-dev.py
chmod +x calendarbuddy-dev.py

# Test your changes
./calendarbuddy-dev.py --dry-run --show-db
```

### Testing
```bash
# Test basic functionality
./calendarbuddy-dev.py --dry-run

# Test parsing with current calendar
./calendarbuddy-dev.py --print-current --format json

# Test change tracking
./calendarbuddy-dev.py  # First run
# (modify a calendar event)
./calendarbuddy-dev.py  # Second run
./calendarbuddy-dev.py --print-changes --since 1h
```

## 📝 Code Style

Please follow these conventions:

### Python Style
- Follow PEP 8 where practical
- Use descriptive variable names
- Add docstrings to functions
- Keep functions focused and testable

### Database Changes
- Always use migrations for schema changes
- Add new columns with `ensure_column()` pattern
- Maintain backwards compatibility
- Test with existing databases

### Example Pattern
```python
def parse_new_event_format(line: str) -> Optional[EventData]:
    """
    Parse a new event format from icalBuddy output.
    
    Args:
        line: Raw line from icalBuddy
        
    Returns:
        EventData object or None if no match
    """
    # Implementation here
    pass
```

## 🚀 Pull Request Process

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes**
4. **Test thoroughly** (see Testing section)
5. **Commit with clear messages**:
   ```bash
   git commit -m "Add support for recurring event parsing
   
   - Parse RRULE patterns in event descriptions
   - Handle weekly/monthly recurrence
   - Add tests for recurring event detection"
   ```
6. **Push to your fork**: `git push origin feature/your-feature-name`
7. **Create a Pull Request**

### PR Requirements
- [ ] Code follows style guidelines
- [ ] Changes are tested on your calendar setup
- [ ] Documentation updated if needed
- [ ] No personal calendar data in commits
- [ ] Backwards compatibility maintained

## 🧪 Testing Guidelines

### Manual Testing Checklist
- [ ] Dry run works: `--dry-run`
- [ ] Basic sync: default behavior
- [ ] Date filtering: `--date`, `--from`, `--to`
- [ ] Output formats: `--format table/json/csv`
- [ ] Change tracking: `--print-changes`
- [ ] Edge cases: empty calendars, malformed events

### Test Data
Create test calendar events with:
- Different date formats
- Time ranges (AM/PM, 24-hour)
- All-day events
- Multi-day events
- Events with meeting URLs
- Events with special characters

## 📚 Documentation Standards

- **README**: Update for new features
- **Inline comments**: Explain complex parsing logic
- **Examples**: Add script examples for new features
- **Help text**: Update `--help` output when needed

## 🏷️ Release Process

Maintainers handle releases, but contributors should:
- Update version in `VERSION = "x.y.z"`
- Add changelog entry for significant changes
- Test on multiple macOS versions when possible

## 📞 Getting Help

- **Discussions**: Use GitHub Discussions for questions
- **Issues**: GitHub Issues for bugs and feature requests  
- **Code Review**: Tag maintainers in PRs for review

## 🎯 Good First Issues

Looking for where to start? Try these:

- **Documentation**: Improve README examples
- **Error handling**: Better error messages
- **Performance**: Add database indexes
- **Testing**: Create test calendar events
- **Integration**: Write example scripts

## 📜 License

By contributing, you agree that your contributions will be licensed under the GNU General Public License v3.0.

---

**Thank you for helping make CalendarBuddy better! 🗓️**
