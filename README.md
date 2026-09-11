# Bhograj Buildtech — Static Real Estate Website

A responsive, animated, multi-page real-estate website for Noida, Greater Noida and Greater Noida West. It uses semantic HTML, CSS and vanilla JavaScript only. There is no build step, backend, database or production dependency.

## Project files

- `index.html` — home experience
- `properties.html` — searchable/filterable listings and query-string details
- `about.html` — story, vision, mission and leadership
- `contact.html` — WhatsApp enquiry form, contact information and FAQ
- `css/` — design system, animations and responsive behaviour
- `js/config.js` — central company/contact configuration
- `js/properties.js` — all demo listing data and rendering
- `js/main.js` / `js/animations.js` — navigation, forms and interactions

## Run locally

Open `index.html` directly, or (recommended for browser-like behaviour) run:

```bash
python -m http.server 8000
```

Then visit `http://localhost:8000`.

## Essential edits before launch

1. **Company details, phone, WhatsApp, email, address and social links:** edit `SITE_CONFIG` in `js/config.js`. Replace the canonical URL and JSON-LD placeholders in `index.html` too.
2. **About Us:** search for `ABOUT US CONTENT START` in `index.html` and `about.html`.
3. **Vision:** search for `VISION CONTENT START` in both files.
4. **Mission:** search for `MISSION CONTENT START` in both files.
5. **Properties:** edit the `PROPERTIES` array in `js/properties.js`; detailed add/remove/image/category instructions are directly above it.
6. **Images:** replace an image URL with a local path such as `assets/images/property-name.webp` or another licensed stable URL. Update `CREDITS.md`.
7. **Logo:** replace the `.logo` text in each HTML file, or place a real logo in `assets/logo/` and use a relative `<img>` path.
8. **Statistics and testimonials:** replace only with genuine, approved information.

The WhatsApp form intentionally warns until the placeholder number is replaced. It does not save user data; it formats the enquiry and opens WhatsApp.

## Deploy to GitHub Pages

1. Create a GitHub repository.
2. Upload/push all project files to it.
3. Open the repository **Settings**.
4. Select **Pages**.
5. Under Source, choose **Deploy from a branch**.
6. Choose `main` (or your published branch).
7. Choose `/(root)` and click **Save**.
8. Wait for GitHub to publish the supplied URL.

Relative links and assets make the website safe for project URLs such as `username.github.io/project-name/`. The `.nojekyll` file ensures direct static publishing.

## Compliance note

The included listings and statistics are explicitly marked as samples/placeholders. Before publishing real property data, verify all ownership, approval, pricing and regulatory information and obtain appropriate legal review.
