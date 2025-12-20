# Build & Test Protocol

## Overview
This protocol ensures the website is tested continuously as it's built. After completing each phase, run the specified tests before moving to the next phase. Do not proceed to the next phase until all tests pass.

---

## Development Server Rule
**IMPORTANT:** Start the dev server at the beginning and keep it running throughout development.

```bash
npm run dev
```

After every component or page is built, check the browser at http://localhost:3000 to verify:
- No console errors
- Page renders correctly
- No visual bugs

---

## Phase 1: Project Scaffold

### Build
- Initialize Next.js 14 project with TypeScript
- Install Tailwind CSS and configure
- Set up folder structure per TECH_REQUIREMENTS.md
- Create basic layout.tsx with metadata
- Create placeholder pages (empty components for each route)

### Test Checklist
```
□ npm run dev starts without errors
□ http://localhost:3000 loads (even if blank)
□ http://localhost:3000/tour loads (even if blank)
□ http://localhost:3000/podcasts loads (even if blank)
□ http://localhost:3000/about loads (even if blank)
□ http://localhost:3000/contact loads (even if blank)
□ No TypeScript errors (npm run build)
□ Tailwind classes work (test with a colored div)
```

### Commands to Run
```bash
npm run dev          # Should start without errors
npm run build        # Should complete without errors
npm run lint         # Should pass
```

**STOP. Verify all tests pass before proceeding.**

---

## Phase 2: Layout Components (Header + Footer)

### Build
- Header component with navigation
- Mobile menu with toggle
- Footer component
- Add to layout.tsx so they appear on all pages

### Test Checklist
```
□ Header displays on all pages
□ Footer displays on all pages
□ Logo/site name visible in header
□ All nav links visible on desktop (Tour, Podcasts, About, Contact)
□ CTA button visible in header ("Get Tickets" or similar)
□ Mobile: Hamburger menu icon appears below 768px
□ Mobile: Clicking hamburger opens mobile menu
□ Mobile: All nav links visible in mobile menu
□ Mobile: Clicking a link closes mobile menu
□ Mobile: Can close menu by clicking hamburger again
□ Footer shows social icons
□ Footer shows copyright text
□ Clicking nav links navigates to correct pages
```

### Browser Tests (Manual)
1. Open http://localhost:3000
2. Resize browser to mobile width (<768px)
3. Click hamburger menu - does it open?
4. Click a nav link - does it navigate and close menu?
5. Resize back to desktop - does full nav appear?

### Commands to Run
```bash
npm run build        # No errors
```

**STOP. Verify all tests pass before proceeding.**

---

## Phase 3: Homepage

### Build
- Hero section (background image, overlay, headline, CTAs)
- Tour dates preview section
- Podcast section
- Newsletter signup section

### Test Checklist
```
□ Hero displays full viewport height (100vh or close)
□ Hero background image loads (check Network tab if not)
□ Hero text is readable (contrast with background)
□ "See Me Live" button links to /tour
□ "Listen to Podcast" button links to /podcasts
□ Tour dates section shows sample dates
□ "View All Dates" links to /tour
□ Podcast section displays show info
□ Platform buttons (Spotify, Apple, YouTube) are visible
□ Newsletter form has email input and submit button
□ Newsletter form shows validation on empty submit
□ All sections stack properly on mobile
□ No horizontal scroll on mobile
□ Images are optimized (use Next.js Image component)
```

### Browser Tests (Manual)
1. Load homepage - does hero fill screen?
2. Scroll down - do all sections appear?
3. Click both hero CTAs - do they navigate correctly?
4. Submit empty newsletter form - does it show validation?
5. Mobile: Does everything stack vertically?
6. Mobile: Is text readable (not too small)?
7. Mobile: Do buttons have adequate tap targets (min 44px)?

### Console Check
```
Open browser DevTools (F12) → Console tab
□ No red errors
□ No 404s for images or resources
```

**STOP. Verify all tests pass before proceeding.**

---

## Phase 4: Tour Page

### Build
- Tour dates list (full list)
- Individual tour date cards/rows
- Ticket buttons
- Empty state
- "Request a show" section

### Test Checklist
```
□ Page loads at /tour
□ All sample tour dates display
□ Each date shows: date, venue, city, ticket button
□ Ticket buttons are clickable (can be # links for now)
□ Dates are in chronological order
□ Sold out state styling works (if applicable)
□ Empty state shows when no dates (test by emptying data)
□ "Request a show" form displays
□ Form has city, email fields
□ Mobile: Cards/rows stack properly
□ Mobile: Ticket buttons are easily tappable
```

### Browser Tests (Manual)
1. Navigate to /tour from homepage
2. Count tour dates - matches data?
3. Click a ticket button - does it respond?
4. Mobile: Can you easily tap ticket buttons?

**STOP. Verify all tests pass before proceeding.**

---

## Phase 5: Podcasts Page

### Build
- Radio Ridley Radio section
- Banana Phone section
- Platform link buttons
- Patreon upsell section

### Test Checklist
```
□ Page loads at /podcasts
□ Radio Ridley Radio section displays
□ Show artwork/image displays
□ Show description displays
□ Platform buttons display (Spotify, Apple, YouTube)
□ Platform buttons have correct icons
□ Banana Phone section displays
□ Patreon section displays with CTA
□ Mobile: Sections stack vertically
□ Mobile: Platform buttons are tappable
```

### Browser Tests (Manual)
1. Navigate to /podcasts
2. Are both shows clearly visible?
3. Click platform buttons - do they have hover states?
4. Mobile: Is show artwork sized appropriately?

**STOP. Verify all tests pass before proceeding.**

---

## Phase 6: About Page

### Build
- Headshot image section
- Bio text section
- Credits/achievements
- Press photos (optional)

### Test Checklist
```
□ Page loads at /about
□ Headshot image displays
□ Bio text is readable
□ Credits section displays
□ Mobile: Image and text stack properly
□ Mobile: Text is readable font size
```

### Browser Tests (Manual)
1. Navigate to /about
2. Is the headshot prominent?
3. Is bio text easy to read?
4. Mobile: Does layout make sense?

**STOP. Verify all tests pass before proceeding.**

---

## Phase 7: Contact Page

### Build
- Contact form
- Booking info section
- Form validation
- Success/error states

### Test Checklist
```
□ Page loads at /contact
□ Booking email displays (RadioRidleyRadio@gmail.com)
□ Contact form displays
□ Form has: Name, Email, Subject dropdown, Message fields
□ Form validates required fields on submit
□ Email field validates email format
□ Submit button has loading state
□ Success message shows after submission
□ Error message shows if submission fails
□ Mobile: Form fields are full width
□ Mobile: Easy to type in fields
```

### Browser Tests (Manual)
1. Navigate to /contact
2. Submit empty form - validation errors?
3. Enter invalid email - validation error?
4. Fill form correctly and submit - success state?
5. Mobile: Tap into each field - keyboard appears?

**STOP. Verify all tests pass before proceeding.**

---

## Phase 8: Cross-Page Testing

### Full Navigation Test
```
□ Home → Tour (via hero CTA)
□ Home → Tour (via nav)
□ Home → Podcasts (via hero CTA)
□ Home → Podcasts (via nav)
□ Home → About (via nav)
□ Home → Contact (via nav)
□ Tour → Home (via logo)
□ Any page → Any page (via nav)
□ Mobile: All navigation works via mobile menu
```

### Responsive Testing
Test at these breakpoints:
```
□ 375px (iPhone SE)
□ 390px (iPhone 12/13/14)
□ 768px (iPad)
□ 1024px (iPad landscape / small laptop)
□ 1440px (desktop)
□ 1920px (large desktop)
```

At each breakpoint verify:
- No horizontal scroll
- Text is readable
- Buttons are tappable
- Images are appropriate size
- Layout makes sense

### Performance Check
```bash
npm run build
```
Then check:
```
□ Build completes without errors
□ No "Large page data" warnings
□ Images are optimized (WebP, proper sizing)
```

**STOP. Verify all tests pass before proceeding.**

---

## Phase 9: Polish & Finishing

### Build
- Favicon
- 404 page
- Meta tags (SEO)
- Open Graph images
- Smooth scroll
- Hover animations
- Loading states

### Test Checklist
```
□ Favicon appears in browser tab
□ /nonexistent-page shows 404 page
□ 404 page has link back to home
□ Page titles are unique per page (check browser tab)
□ Smooth scroll works on anchor links
□ Buttons have hover effects
□ Cards have hover effects
□ Form buttons show loading state when submitting
```

### SEO Check
View page source (Ctrl+U) and verify:
```
□ <title> tag present and descriptive
□ <meta name="description"> present
□ <meta property="og:title"> present
□ <meta property="og:description"> present
□ <meta property="og:image"> present
```

### Final Build Test
```bash
npm run build        # Must pass
npm run start        # Test production build locally
```

Browse the production build at http://localhost:3000 and repeat key tests.

---

## Quick Reference Commands

```bash
# Start dev server (keep running)
npm run dev

# Check for TypeScript/build errors
npm run build

# Check for linting issues
npm run lint

# Test production build
npm run build && npm run start
```

---

## If Tests Fail

1. **Console errors:** Read the error message, fix the issue, save, check again
2. **Page not loading:** Check terminal for build errors
3. **Styling broken:** Check Tailwind classes, ensure Tailwind is configured
4. **Images not loading:** Check file paths, use Next.js Image component
5. **Links not working:** Check href values, ensure pages exist
6. **Mobile issues:** Check responsive classes (sm:, md:, lg:)

---

## Sign-Off Checklist

Before considering the site complete:

```
□ All pages load without errors
□ All navigation works
□ All forms validate and submit
□ Mobile responsive at all breakpoints
□ No console errors
□ npm run build passes
□ Lighthouse score 90+ (run in Chrome DevTools)
□ All images load
□ All links work
□ Favicon displays
□ Meta tags present
```

Site is ready for client review when all boxes are checked.
