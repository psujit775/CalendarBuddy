#!/bin/bash
# CalendarBuddy Setup Script
# Copyright (C) 2025 - Licensed under GNU GPL v3.0

set -e  # Exit on any error

echo "🗓️  CalendarBuddy Setup"
echo "======================"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}❌ Error: CalendarBuddy requires macOS${NC}"
    exit 1
fi

echo -e "${BLUE}📋 Checking prerequisites...${NC}"

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed${NC}"
    echo "Install Python 3 from https://python.org or use Homebrew: brew install python"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✅ Python ${PYTHON_VERSION} found${NC}"

# Check for icalBuddy
if ! command -v icalBuddy &> /dev/null; then
    echo -e "${YELLOW}⚠️  icalBuddy not found${NC}"
    
    # Check if Homebrew is installed
    if command -v brew &> /dev/null; then
        echo -e "${BLUE}📦 Installing icalBuddy via Homebrew...${NC}"
        brew install ical-buddy
        echo -e "${GREEN}✅ icalBuddy installed${NC}"
    else
        echo -e "${RED}❌ Please install icalBuddy manually:${NC}"
        echo "   1. Install Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        echo "   2. Install icalBuddy: brew install ical-buddy"
        echo "   Or download from: https://hasseg.org/icalBuddy/"
        exit 1
    fi
else
    echo -e "${GREEN}✅ icalBuddy found${NC}"
fi

# Test icalBuddy
echo -e "${BLUE}🧪 Testing icalBuddy...${NC}"
if icalBuddy eventsToday > /dev/null 2>&1; then
    echo -e "${GREEN}✅ icalBuddy working correctly${NC}"
else
    echo -e "${YELLOW}⚠️  icalBuddy test failed - this might be normal if no events today${NC}"
fi

# Install CalendarBuddy
INSTALL_PATH="$HOME/calendarbuddy.py"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

if [[ -f "$SCRIPT_DIR/calendarbuddy.py" ]]; then
    echo -e "${BLUE}📁 Installing CalendarBuddy to ${INSTALL_PATH}...${NC}"
    cp "$SCRIPT_DIR/calendarbuddy.py" "$INSTALL_PATH"
    chmod +x "$INSTALL_PATH"
    echo -e "${GREEN}✅ CalendarBuddy installed${NC}"
else
    echo -e "${YELLOW}⚠️  calendarbuddy.py not found in current directory${NC}"
    echo "Please ensure you're running this from the CalendarBuddy repository directory"
fi

# Test installation
echo -e "${BLUE}🧪 Testing CalendarBuddy installation...${NC}"
if "$INSTALL_PATH" --version > /dev/null 2>&1; then
    VERSION=$("$INSTALL_PATH" --version)
    echo -e "${GREEN}✅ $VERSION installed successfully${NC}"
else
    echo -e "${RED}❌ CalendarBuddy installation test failed${NC}"
    exit 1
fi

# Initial sync
echo -e "${BLUE}🔄 Running initial calendar sync...${NC}"
if "$INSTALL_PATH" --dry-run; then
    echo -e "${GREEN}✅ Dry run successful${NC}"
    
    read -p "Run actual sync now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        "$INSTALL_PATH"
        echo -e "${GREEN}✅ Initial sync complete${NC}"
    fi
else
    echo -e "${RED}❌ Sync test failed${NC}"
    exit 1
fi

# Offer to setup cron job
echo
echo -e "${BLUE}⏰ Cron Job Setup${NC}"
echo "Would you like to set up automatic syncing?"
echo "This will sync your calendar every 30 minutes."
echo
read -p "Setup cron job? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Create cron job
    CRON_JOB="*/30 * * * * /usr/bin/python3 $INSTALL_PATH >> /tmp/calendarbuddy.log 2>&1"
    
    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "calendarbuddy.py"; then
        echo -e "${YELLOW}⚠️  CalendarBuddy cron job already exists${NC}"
    else
        # Add to crontab
        (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
        echo -e "${GREEN}✅ Cron job added - syncing every 30 minutes${NC}"
        echo "Logs will be written to /tmp/calendarbuddy.log"
    fi
fi

echo
echo -e "${GREEN}🎉 Setup Complete!${NC}"
echo
echo -e "${BLUE}Quick Start Commands:${NC}"
echo "  View today's events:     $INSTALL_PATH --print-current"
echo "  View specific date:      $INSTALL_PATH --print-current --date 2025-12-25"
echo "  View recent changes:     $INSTALL_PATH --print-changes --since 24h"
echo "  Manual sync:             $INSTALL_PATH"
echo "  Get help:                $INSTALL_PATH --help"
echo
echo -e "${BLUE}Database location:${NC} ~/.calendar_events.db"
echo -e "${BLUE}Documentation:${NC} https://github.com/yourusername/CalendarBuddy"
echo
echo "Happy calendaring! 📅"
