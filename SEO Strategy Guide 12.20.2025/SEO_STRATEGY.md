# 🎯 SEO Strategy: Funny Over Everything
## Dominating Austin Comedy Search Results

---

## Executive Summary

Your goal: When someone searches for comedy shows in Austin, FOE should be on page 1.

**Target Keywords:**
- "comedy shows austin"
- "comedy in austin texas"
- "austin comedy tonight"
- "comedy shows near me" (Austin area)
- "where to see comedy in austin"
- "best comedy clubs austin tx"
- "live comedy austin"
- "stand up comedy austin"

**The Strategy:** Local SEO + Event Schema + Content Marketing

---

## Part 1: On-Page SEO Fundamentals

### 1.1 Title Tags (Most Important!)

Every page needs a unique, keyword-rich title tag.

```html
<!-- Homepage -->
<title>Comedy Shows in Austin TX | Tonight's Shows & Tickets | Funny Over Everything</title>

<!-- Shows Page -->
<title>Austin Comedy Shows This Week | Live Stand-Up Tonight | FOE ATX</title>

<!-- Mission/About Page -->
<title>About Funny Over Everything | Austin's Comedy Show Guide | FOE</title>
```

**Best Practices:**
- Keep under 60 characters
- Put main keyword near the front
- Include "Austin" or "ATX" in every title
- Make it compelling (people need to want to click)

### 1.2 Meta Descriptions

```html
<!-- Homepage -->
<meta name="description" content="Find the best comedy shows in Austin, Texas tonight. Creek and the Cave, Comedy Mothership, Cap City & more. Get tickets to live stand-up comedy near you. Updated daily.">

<!-- Shows Page -->
<meta name="description" content="Complete list of Austin comedy shows this week. Stand-up, improv & open mics at Creek and the Cave, Mothership, Velveeta Room & more. Tickets & showtimes updated daily.">
```

**Best Practices:**
- 150-160 characters
- Include primary keyword
- Include call-to-action ("Get tickets", "Find shows")
- Mention specific venues (people search for these!)

### 1.3 Header Tags (H1, H2, H3)

```html
<!-- Homepage Structure -->
<h1>Find Comedy Shows in Austin, TX</h1>

<h2>Tonight's Top Pick</h2>
<!-- featured show -->

<h2>This Week's Featured Shows</h2>
<!-- show cards -->

<h2>Austin Comedy Venues</h2>
<h3>Creek and the Cave</h3>
<h3>Comedy Mothership</h3>
<h3>Cap City Comedy Club</h3>

<h2>Find Comedy Near You</h2>
```

**Rules:**
- Only ONE H1 per page
- H1 should contain your main keyword
- Use H2s for major sections
- Use H3s for subsections

### 1.4 URL Structure

Good URLs:
```
funnyovereverything.com/shows
funnyovereverything.com/shows/tonight
funnyovereverything.com/shows/this-week
funnyovereverything.com/venues/creek-and-the-cave
funnyovereverything.com/venues/comedy-mothership
```

Bad URLs:
```
funnyovereverything.com/page1
funnyovereverything.com/shows?id=12345
funnyovereverything.com/s/12-20-2024
```

### 1.5 Image Alt Text

```html
<!-- Good alt text -->
<img src="comedian.jpg" alt="Josh Potter performing stand-up comedy at Creek and the Cave Austin">

<!-- Bad alt text -->
<img src="comedian.jpg" alt="image1">
<img src="comedian.jpg" alt=""> <!-- empty is worst -->
```

**Include in alt text:**
- Performer name
- Venue name
- "Austin" or "ATX"
- "comedy" or "stand-up"

---

## Part 2: Local SEO (Critical for "Near Me" Searches)

### 2.1 Google Business Profile

Even though FOE is a listing site (not a physical venue), consider:

**Option A: Create a GBP as "Service Area Business"**
- Category: "Entertainment Website" or "Event Ticket Seller"
- Service area: Austin, TX metro
- This helps for "comedy shows near me" searches

**Option B: Focus on being listed/linked by venue GBPs**
- Reach out to venues
- Ask them to link to your site
- Get mentioned in their posts

### 2.2 NAP Consistency

If you have any business info (even just email):
```
Funny Over Everything
Austin, TX
foeatx@gmail.com
```

Keep this IDENTICAL everywhere it appears:
- Website footer
- Social media profiles
- Any directories

### 2.3 Local Keywords Throughout Site

Sprinkle these naturally in your content:

**Primary Location Keywords:**
- Austin, TX
- Austin, Texas
- ATX
- Central Texas

**Neighborhood Keywords:**
- Downtown Austin
- East Austin
- South Austin
- 6th Street
- Rainey Street

**Example Copy:**
> "Find the best comedy shows in **Austin, Texas** tonight. From **downtown** venues like Creek and the Cave to **East Austin's** hidden gems, we've got every **ATX** comedy show covered."

### 2.4 Venue-Specific Pages (Huge Opportunity!)

Create dedicated pages for each venue:

```
/venues/creek-and-the-cave
/venues/comedy-mothership
/venues/cap-city-comedy
/venues/velveeta-room
/venues/sunset-strip-atx
```

Each page should include:
- Venue name + "Austin comedy"
- Address with Google Maps embed
- Upcoming shows at that venue
- Description of the venue
- Link to venue's ticket page

**This captures searches like:**
- "Creek and the Cave shows"
- "Comedy Mothership schedule"
- "Cap City Comedy tonight"

---

## Part 3: Event Schema Markup (Get Rich Results!)

### 3.1 What is Event Schema?

Schema markup tells Google "this is an event" so it can display rich results:

```
🎤 Josh Potter - Live Stand-Up
📍 Creek and the Cave, Austin TX
📅 Dec 21, 2024 • 8:00 PM
🎟️ Tickets from $25
```

This appears directly in search results = MORE CLICKS!

### 3.2 Event Schema Code Template

Add this to each show listing:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "ComedyEvent",
  "name": "Josh Potter - Live Stand-Up Comedy",
  "description": "Josh Potter brings his hilarious stand-up to Austin for one night only at Creek and the Cave.",
  "image": "https://funnyovereverything.com/images/josh-potter.jpg",
  "startDate": "2024-12-21T20:00:00-06:00",
  "endDate": "2024-12-21T22:00:00-06:00",
  "eventStatus": "https://schema.org/EventScheduled",
  "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
  "location": {
    "@type": "Place",
    "name": "Creek and the Cave",
    "address": {
      "@type": "PostalAddress",
      "streetAddress": "611 E 7th St",
      "addressLocality": "Austin",
      "addressRegion": "TX",
      "postalCode": "78701",
      "addressCountry": "US"
    }
  },
  "performer": {
    "@type": "Person",
    "name": "Josh Potter"
  },
  "organizer": {
    "@type": "Organization",
    "name": "Creek and the Cave",
    "url": "https://www.creekandcave.com"
  },
  "offers": {
    "@type": "Offer",
    "url": "https://www.creekandcave.com/events/josh-potter",
    "price": "25.00",
    "priceCurrency": "USD",
    "availability": "https://schema.org/InStock",
    "validFrom": "2024-11-01T00:00:00-06:00"
  }
}
</script>
```

### 3.3 Website/Organization Schema

Add to every page (in `<head>`):

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Funny Over Everything",
  "alternateName": "FOE ATX",
  "url": "https://funnyovereverything.com",
  "description": "Austin's complete guide to comedy shows, stand-up, and live entertainment.",
  "publisher": {
    "@type": "Organization",
    "name": "Funny Over Everything",
    "logo": {
      "@type": "ImageObject",
      "url": "https://funnyovereverything.com/images/logo.jpg"
    }
  },
  "potentialAction": {
    "@type": "SearchAction",
    "target": "https://funnyovereverything.com/search?q={search_term_string}",
    "query-input": "required name=search_term_string"
  }
}
</script>
```

### 3.4 Local Business Schema (Optional)

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "Funny Over Everything",
  "@id": "https://funnyovereverything.com",
  "url": "https://funnyovereverything.com",
  "email": "foeatx@gmail.com",
  "description": "Austin's comedy show guide - find stand-up, improv, and live comedy events.",
  "areaServed": {
    "@type": "City",
    "name": "Austin",
    "sameAs": "https://en.wikipedia.org/wiki/Austin,_Texas"
  },
  "sameAs": [
    "https://www.instagram.com/willmuss87/"
  ]
}
</script>
```

### 3.5 Testing Your Schema

Use these tools to verify:
1. **Google Rich Results Test**: https://search.google.com/test/rich-results
2. **Schema Markup Validator**: https://validator.schema.org/

---

## Part 4: Content Strategy

### 4.1 Blog/Content Ideas

Create content that people search for:

**"Best of" Lists (High Search Volume):**
- "10 Best Comedy Clubs in Austin TX"
- "Best Open Mics in Austin for Comedians"
- "Where to See Free Comedy in Austin"
- "Austin's Best Late Night Comedy Shows"

**"Tonight/This Week" Content:**
- "Comedy Shows in Austin Tonight" (update daily)
- "This Weekend's Comedy Shows in Austin"
- "New Year's Eve Comedy Shows Austin 2024"

**Venue Guides:**
- "Creek and the Cave: Complete Guide to Austin's Best Comedy Club"
- "Comedy Mothership: Joe Rogan's Austin Club - What to Expect"
- "Cap City Comedy Club: Austin's Original Comedy Venue"

**How-To Content:**
- "How to Get Into Austin's Comedy Scene"
- "Austin Comedy for Beginners: Where to Start"
- "How to Get Tickets to Sold-Out Comedy Shows in Austin"

### 4.2 FAQ Section (Great for SEO!)

Add an FAQ section to your homepage:

```html
<section class="faq">
  <h2>Frequently Asked Questions About Austin Comedy</h2>
  
  <div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
    <h3 itemprop="name">Where can I see comedy shows in Austin tonight?</h3>
    <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
      <p itemprop="text">Austin has comedy shows every night at venues like Creek and the Cave, Comedy Mothership, Cap City Comedy Club, and The Velveeta Room. Check our homepage for tonight's complete lineup.</p>
    </div>
  </div>
  
  <div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
    <h3 itemprop="name">What is the best comedy club in Austin?</h3>
    <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
      <p itemprop="text">Austin's top comedy clubs include Creek and the Cave (known for national headliners), Comedy Mothership (Joe Rogan's club), and Cap City Comedy Club (Austin's original comedy venue since 1986).</p>
    </div>
  </div>
  
  <div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
    <h3 itemprop="name">How much do comedy show tickets cost in Austin?</h3>
    <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
      <p itemprop="text">Comedy show tickets in Austin typically range from $10-15 for local showcases and open mics, $20-40 for touring comedians, and $50+ for major headliners and special events.</p>
    </div>
  </div>
</section>
```

### 4.3 Internal Linking

Link between your pages strategically:

```
Homepage → links to → Shows Page, Venue Pages
Shows Page → links to → Individual Show Pages, Venue Pages
Venue Pages → links to → Shows at That Venue, Homepage
```

Use keyword-rich anchor text:
```html
<!-- Good -->
<a href="/venues/creek-and-the-cave">See all shows at Creek and the Cave</a>

<!-- Bad -->
<a href="/venues/creek-and-the-cave">Click here</a>
```

---

## Part 5: Technical SEO

### 5.1 Site Speed

Comedy fans are impatient! Optimize for speed:

- Compress images (use WebP format)
- Minify CSS/JS
- Use lazy loading for images
- Enable browser caching
- Use a CDN (Cloudflare is free)

**Test with:** https://pagespeed.web.dev/

### 5.2 Mobile-First

Over 60% of local searches are mobile. Ensure:

- Responsive design
- Tap targets are large enough (44x44px minimum)
- Text is readable without zooming
- No horizontal scrolling

### 5.3 HTTPS

Your site MUST be HTTPS. Google penalizes non-secure sites.

### 5.4 XML Sitemap

Create and submit a sitemap:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://funnyovereverything.com/</loc>
    <lastmod>2024-12-20</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://funnyovereverything.com/shows</loc>
    <lastmod>2024-12-20</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <!-- Add all pages -->
</urlset>
```

Submit to:
- Google Search Console
- Bing Webmaster Tools

### 5.5 Robots.txt

```
User-agent: *
Allow: /

Sitemap: https://funnyovereverything.com/sitemap.xml
```

---

## Part 6: Off-Page SEO

### 6.1 Backlink Opportunities

**Local Austin Sites:**
- Austin Chronicle (event listings)
- Do512.com
- Austin360
- Austin Monthly
- CultureMap Austin

**Comedy Sites:**
- Comedy venue websites (ask for a link!)
- Austin comedy Facebook groups
- Reddit r/Austin, r/AustinComedy

**Directories:**
- Yelp (create a listing)
- TripAdvisor
- Google Maps (if applicable)

### 6.2 Social Signals

Active social presence helps SEO:

**Instagram:**
- Post daily show highlights
- Use hashtags: #AustinComedy #ATXComedy #AustinNightlife #LiveComedy
- Tag venues and performers

**Twitter/X:**
- Tweet tonight's shows
- Engage with Austin comedy accounts
- Use location tags

### 6.3 Local Partnerships

Partner with:
- Comedy venues (cross-promotion)
- Austin food/drink blogs
- Local podcasts
- Austin influencers

---

## Part 7: Quick Wins (Do These First!)

### Week 1: Foundation
- [ ] Add proper title tags to all pages
- [ ] Add meta descriptions to all pages
- [ ] Add H1 tags with keywords
- [ ] Add alt text to all images

### Week 2: Schema
- [ ] Add Website schema to all pages
- [ ] Add Event schema to show listings
- [ ] Test with Google Rich Results Tool
- [ ] Fix any schema errors

### Week 3: Content
- [ ] Add FAQ section to homepage
- [ ] Write "Comedy Shows in Austin Tonight" page
- [ ] Create at least 2 venue pages
- [ ] Add internal links between pages

### Week 4: Technical
- [ ] Ensure mobile responsiveness
- [ ] Test and improve page speed
- [ ] Create XML sitemap
- [ ] Submit to Google Search Console

---

## Part 8: Tracking Success

### 8.1 Google Search Console (Free)

Set up and monitor:
- Which keywords you're ranking for
- Click-through rates
- Any crawl errors
- Mobile usability issues

### 8.2 Google Analytics (Free)

Track:
- Total visitors
- Where traffic comes from
- Most popular pages
- Time on site

### 8.3 Keyword Rankings

Track rankings for:
- "comedy shows austin"
- "austin comedy tonight"
- "stand up comedy austin tx"
- "creek and the cave shows"
- "comedy mothership austin"

Use: Ubersuggest (free), SEMrush, or Ahrefs

---

## Part 9: Sample Homepage Meta Tags

Copy this into your `<head>`:

```html
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  
  <!-- Primary Meta Tags -->
  <title>Comedy Shows in Austin TX | Tonight's Shows & Tickets | Funny Over Everything</title>
  <meta name="title" content="Comedy Shows in Austin TX | Tonight's Shows & Tickets | Funny Over Everything">
  <meta name="description" content="Find the best comedy shows in Austin, Texas tonight. Creek and the Cave, Comedy Mothership, Cap City & more. Get tickets to live stand-up comedy near you.">
  <meta name="keywords" content="austin comedy, comedy shows austin, austin comedy tonight, stand up comedy austin tx, creek and the cave, comedy mothership, cap city comedy, austin entertainment">
  <meta name="author" content="Funny Over Everything">
  <meta name="robots" content="index, follow">
  
  <!-- Open Graph / Facebook -->
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://funnyovereverything.com/">
  <meta property="og:title" content="Comedy Shows in Austin TX | Funny Over Everything">
  <meta property="og:description" content="Find the best comedy shows in Austin, Texas tonight. Updated daily with tickets and showtimes.">
  <meta property="og:image" content="https://funnyovereverything.com/images/og-image.jpg">
  <meta property="og:locale" content="en_US">
  <meta property="og:site_name" content="Funny Over Everything">
  
  <!-- Twitter -->
  <meta property="twitter:card" content="summary_large_image">
  <meta property="twitter:url" content="https://funnyovereverything.com/">
  <meta property="twitter:title" content="Comedy Shows in Austin TX | Funny Over Everything">
  <meta property="twitter:description" content="Find the best comedy shows in Austin, Texas tonight. Updated daily with tickets and showtimes.">
  <meta property="twitter:image" content="https://funnyovereverything.com/images/og-image.jpg">
  
  <!-- Geo Tags for Local SEO -->
  <meta name="geo.region" content="US-TX">
  <meta name="geo.placename" content="Austin">
  <meta name="geo.position" content="30.2672;-97.7431">
  <meta name="ICBM" content="30.2672, -97.7431">
  
  <!-- Canonical URL -->
  <link rel="canonical" href="https://funnyovereverything.com/">
  
  <!-- Favicon -->
  <link rel="icon" type="image/png" href="/favicon.png">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
</head>
```

---

## Summary: The SEO Formula

```
Keyword-Rich Title Tags
+ Meta Descriptions with CTAs
+ Event Schema Markup
+ Local Keywords (Austin, ATX)
+ Quality Content (venue pages, FAQs)
+ Fast Mobile Site
+ Backlinks from Local Sites
= Page 1 Rankings 🎯
```

---

## Need Help Implementing?

This document is your roadmap. Work through it section by section:

1. **Start with title tags and meta descriptions** (biggest impact)
2. **Add event schema** (gets you rich results)
3. **Create venue pages** (captures long-tail searches)
4. **Build backlinks** (authority signals)

Give it 3-6 months of consistent effort and you'll see results. SEO is a marathon, not a sprint!

Good luck dominating Austin comedy search! 🎤🔥
