#!/bin/bash
# Slack Calendar Notification Script
# Sends next meeting info to Slack webhook
#
# Setup:
# 1. Create a Slack App and get webhook URL
# 2. Set SLACK_WEBHOOK_URL environment variable
# 3. Run this script via cron: */15 * * * * /path/to/slack-notify.sh
#
# Copyright (C) 2025 - Licensed under GNU GPL v3.0

set -e

CALENDARBUDDY="$HOME/calendarbuddy.py"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL}"

# Configuration
NOTIFY_MINUTES_BEFORE=15  # Notify 15 minutes before meetings
CHANNEL="#calendar"       # Slack channel to post to

# Check if CalendarBuddy is installed
if [[ ! -f "$CALENDARBUDDY" ]]; then
    echo "❌ CalendarBuddy not found at $CALENDARBUDDY"
    exit 1
fi

# Check if Slack webhook is configured
if [[ -z "$SLACK_WEBHOOK_URL" ]]; then
    echo "❌ SLACK_WEBHOOK_URL environment variable not set"
    echo "Set it with: export SLACK_WEBHOOK_URL='your-webhook-url'"
    exit 1
fi

# Get today's events
TODAY=$(date +%Y-%m-%d)
EVENTS_JSON=$($CALENDARBUDDY --print-current --date $TODAY --format json)

# Check if we have events
if [[ "$EVENTS_JSON" == "[]" ]]; then
    # No events today - maybe send a "free day" message (optional)
    # curl -X POST -H 'Content-type: application/json' \
    #   --data "{\"text\":\"📅 No meetings scheduled today - enjoy your focus time!\", \"channel\":\"$CHANNEL\"}" \
    #   "$SLACK_WEBHOOK_URL"
    exit 0
fi

# Get current time
CURRENT_TIME=$(date +%Y-%m-%dT%H:%M:%S)

# Find next meeting
NEXT_MEETING=$(echo "$EVENTS_JSON" | jq -r --arg current "$CURRENT_TIME" '
  map(select(.start_time > $current)) | 
  sort_by(.start_time) | 
  .[0] // empty
')

if [[ -z "$NEXT_MEETING" || "$NEXT_MEETING" == "null" ]]; then
    echo "No upcoming meetings today"
    exit 0
fi

# Parse next meeting details
TITLE=$(echo "$NEXT_MEETING" | jq -r '.title')
START_TIME=$(echo "$NEXT_MEETING" | jq -r '.start_time')
MEETING_LINK=$(echo "$NEXT_MEETING" | jq -r '.meeting_link // empty')

# Convert start time to readable format
if command -v gdate >/dev/null 2>&1; then
    # GNU date (if installed via brew install coreutils)
    MEETING_TIME=$(gdate -d "$START_TIME" "+%I:%M %p")
    MINUTES_UNTIL=$(( ($(gdate -d "$START_TIME" +%s) - $(gdate +%s)) / 60 ))
else
    # BSD date (macOS default)
    MEETING_TIME=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$START_TIME" "+%I:%M %p" 2>/dev/null || echo "$START_TIME")
    # Simple minutes calculation (less precise)
    HOUR=$(echo "$START_TIME" | cut -d'T' -f2 | cut -d':' -f1)
    MINUTE=$(echo "$START_TIME" | cut -d':' -f2)
    CURRENT_HOUR=$(date +%H)
    CURRENT_MINUTE=$(date +%M)
    MINUTES_UNTIL=$(( ($HOUR - $CURRENT_HOUR) * 60 + ($MINUTE - $CURRENT_MINUTE) ))
fi

# Check if we should notify (within notification window)
if [[ $MINUTES_UNTIL -le $NOTIFY_MINUTES_BEFORE && $MINUTES_UNTIL -gt 0 ]]; then
    # Prepare message
    MESSAGE="🔔 Meeting reminder: *$TITLE* starts in $MINUTES_UNTIL minutes ($MEETING_TIME)"
    
    if [[ -n "$MEETING_LINK" ]]; then
        MESSAGE="$MESSAGE\n🔗 Join: $MEETING_LINK"
    fi
    
    # Create Slack payload
    PAYLOAD=$(jq -n \
        --arg msg "$MESSAGE" \
        --arg channel "$CHANNEL" \
        '{
            text: $msg,
            channel: $channel,
            username: "CalendarBuddy",
            icon_emoji: ":calendar:",
            attachments: [
                {
                    color: "warning",
                    fields: [
                        {
                            title: "Meeting",
                            value: $msg,
                            short: false
                        }
                    ]
                }
            ]
        }')
    
    # Send to Slack
    curl -X POST \
        -H 'Content-type: application/json' \
        --data "$PAYLOAD" \
        "$SLACK_WEBHOOK_URL"
    
    echo "✅ Sent notification for: $TITLE"
    
elif [[ $MINUTES_UNTIL -le 0 ]]; then
    echo "Meeting has already started: $TITLE"
else
    echo "Next meeting '$TITLE' is in $MINUTES_UNTIL minutes (notification threshold: $NOTIFY_MINUTES_BEFORE min)"
fi
