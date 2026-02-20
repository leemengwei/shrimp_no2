Field ops scripts

- user_activity_tracker.py: poll Data API + Gamma API for a single user and print new activity/trades/comments.
- report.py: fetch user data once and write report.md.

Setup:
- Edit USER_ID in user_activity_tracker.py and report.py

Usage:
- python3 user_activity_tracker.py
- python3 report.py

Environment variables:
- INTERVAL: polling interval in seconds (default 60)
