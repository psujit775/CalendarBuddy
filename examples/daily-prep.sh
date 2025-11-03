#!/bin/bash
# Daily Preparation Script
# Uses CalendarBuddy to show today's schedule, recent changes, and tomorrow's prep
#
# Usage: ./daily-prep.sh
# 
# Note: For best results, run 'calendarbuddy.py --lookback 7' weekly to catch
# retroactive calendar changes and ensure your database is up to date.
#
# Lookback options:
# - Default (0): Today only - fast, good for daily cron jobs
# - --lookback 7: Last 7 days - recommended for weekly maintenance  
# - --lookback 30: Last 30 days - good for initial setup or after vacation
# 
# Copyright (C) 2025 - Licensed under GNU GPL v3.0

# Colors for better readability
BLUE='\033[1;34m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CALENDARBUDDY="$HOME/calendarbuddy.py"

# Check if CalendarBuddy is installed
if [[ ! -f "$CALENDARBUDDY" ]]; then
    echo "❌ CalendarBuddy not found at $CALENDARBUDDY"
    echo "Please run the setup script first."
    exit 1
fi

echo -e "${BLUE}📅 Daily Calendar Brief - $(date '+%A, %B %d, %Y')${NC}"
echo "================================================================="
echo

# Today's Schedule
echo -e "${GREEN}🗓️  TODAY'S SCHEDULE${NC}"
echo "-------------------"
if ! $CALENDARBUDDY --view --date $(date +%Y-%m-%d) --format table; then
    echo "No events scheduled for today"
fi
echo

# # Recent Changes (last 24 hours)
# echo -e "${YELLOW}📝 RECENT CHANGES (Last 24h)${NC}"
# echo "-----------------------------"
# CHANGES=$($CALENDARBUDDY --print-changes --since 24h --format table)
# if [[ -z "$CHANGES" || "$CHANGES" == *"ts  action  uid  title  start_time  end_time  meeting_link"* && $(echo "$CHANGES" | wc -l) -le 2 ]]; then
#     echo "No calendar changes in the last 24 hours"
# else
#     echo "$CHANGES"
# fi
# echo

# Tomorrow's Prep
TOMORROW=$(date -j -v+1d +%Y-%m-%d)
echo -e "${BLUE}⏭️  TOMORROW'S SCHEDULE ($TOMORROW)${NC}"
echo "--------------------------------------------"
if ! $CALENDARBUDDY --view --date $TOMORROW --format table; then
    echo "No events scheduled for tomorrow"
fi
echo

# This Week Overview (next 7 days)
echo -e "${GREEN}📊 THIS WEEK OVERVIEW${NC}"
echo "---------------------"
WEEK_END=$(date -j -v+7d +%Y-%m-%d)
WEEK_COUNT=$($CALENDARBUDDY --view --from $(date +%Y-%m-%d) --to $WEEK_END --format csv | tail -n +2 | wc -l | tr -d ' ')
echo "Total events next 7 days: $WEEK_COUNT"

echo "================================================================="
echo -e "${BLUE}💡 Tip: Run 'calendarbuddy.py --help' for more options${NC}"
