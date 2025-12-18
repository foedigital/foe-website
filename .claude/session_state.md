# Claude Session State

This file tracks the current working state so Claude can resume after a conversation limit.

## Last Updated
2025-12-15

## Current Task
COMPLETED - Added Speakeasy venue and Pop Up filter category

## Status: DONE

### What Was Accomplished
1. Added Speakeasy venue to database (venue_id: 9)
2. Downloaded images for The Thursday Special and Sunday Service shows
3. Added both shows to database with times (8:00 PM) and FREE status
4. Created "Pop Up" filter category that groups Bull's Pub, Gnar Bar, and Speakeasy
5. Show cards display actual venue name while filter uses "Pop Up" category

### Speakeasy Shows Added
- The Thursday Special: Thursday, 8:00 PM, FREE
- Sunday Service: Sunday, 8:00 PM, FREE

### Pop Up Category
Venues grouped under "Pop Up" filter:
- Bull's Pub
- Gnar Bar
- Speakeasy

### Site Stats
- Total shows: 72
- Total venues: 7 (6 in filters due to Pop Up grouping)
- Free shows: 20
- Paid shows: 52

## Important Context
- On branch: experimental-v3
- Speakeasy shows link to Eventbrite
- Pop Up filter uses data-venue="pop-up" while cards show actual venue name
- All Speakeasy shows are FREE

## Notes
- User wants session state to persist across conversation limits
- Time displayed as subtle orange text next to venue name
