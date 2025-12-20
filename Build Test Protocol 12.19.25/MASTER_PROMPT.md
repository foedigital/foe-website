# Master Prompt for Claude Code

Copy and paste this entire prompt into VS Code terminal with Claude Code:

---

```
Read all documentation files before starting:
- CLAUDE.md (project brief)
- docs/BRAND.md (colors, fonts, styling)
- docs/CONTENT.md (website copy)
- docs/TECH_REQUIREMENTS.md (tech stack)
- docs/DESIGN_REFERENCES.md (design inspiration)
- BUILD_TEST_PROTOCOL.md (build and test workflow)

You must follow BUILD_TEST_PROTOCOL.md exactly. This means:
1. Complete one phase at a time
2. After each phase, run the tests specified
3. Do not proceed to the next phase until all tests pass
4. Keep npm run dev running and check the browser after each component

## Project: Michael Ridley Comedy Website

Build a complete website following the phased approach in BUILD_TEST_PROTOCOL.md:

**Phase 1:** Scaffold Next.js 14 + TypeScript + Tailwind project. Create folder structure and placeholder pages. Run tests. Stop and confirm.

**Phase 2:** Build Header (with mobile menu) and Footer components. Add to layout. Run tests. Stop and confirm.

**Phase 3:** Build Homepage - hero, tour preview, podcast section, newsletter signup. Use images from /Images folder. Run tests. Stop and confirm.

**Phase 4:** Build Tour page - full tour dates list, ticket buttons, empty state, request form. Run tests. Stop and confirm.

**Phase 5:** Build Podcasts page - Radio Ridley Radio, Banana Phone, platform links, Patreon upsell. Run tests. Stop and confirm.

**Phase 6:** Build About page - headshot, bio, credits. Run tests. Stop and confirm.

**Phase 7:** Build Contact page - contact form with validation, booking info. Run tests. Stop and confirm.

**Phase 8:** Cross-page testing - verify all navigation, test all breakpoints. Run tests. Stop and confirm.

**Phase 9:** Polish - favicon, 404 page, meta tags, animations, loading states. Run final tests.

## Key Requirements
- Mobile-first responsive design
- Green "Frogman" theme (subtle, per BRAND.md)
- Use actual images from /Images folder
- Newsletter signup appears multiple times (hero, section, footer)
- Tour dates prominent and easy to find
- Platform buttons for podcasts (Spotify, Apple, YouTube)
- Contact form with validation

## After Each Phase
1. Run npm run dev (keep it running)
2. Check http://localhost:3000 in browser
3. Run through the test checklist for that phase
4. Report what works and what needs fixing
5. Fix any issues before proceeding
6. Confirm "Phase X complete, all tests pass" before moving on

## Start Now
Begin with Phase 1. After completing the scaffold, show me the folder structure and confirm all Phase 1 tests pass before proceeding to Phase 2.
```

---

## What to Expect

Claude Code will:
1. Build Phase 1 (scaffold)
2. Tell you to check the tests
3. Wait for confirmation or fix issues
4. Move to Phase 2
5. Repeat until complete

## How to Respond

After each phase, Claude will pause. You can say:

- **"All tests pass, continue to Phase X"** - if everything works
- **"The mobile menu doesn't open, fix it"** - if something is broken
- **"The hero image isn't loading, the file is at /Images/michael-stage.jpg"** - to give specific guidance
- **"Show me what the homepage looks like"** - if you want a summary

## Troubleshooting Commands

If something breaks:
```
Check the console for errors and fix them
```

If you want to see current status:
```
Run npm run dev and tell me what pages are working
```

If you want to restart a phase:
```
Rebuild Phase X from scratch following the protocol
```

If the dev server dies:
```
Restart npm run dev and continue
```
