# Week 14: Public Deployment and Final Improvements

## Objective

To deploy BloodLine publicly so it can be demonstrated without a local setup, and to fix the problems found while using the live version.

## Work Done

- Deployed the application on Render's free tier: the frontend as a static site and the FastAPI backend as a Docker web service, with a Neon PostgreSQL database. Pushes to `master` redeploy both services automatically.
  - Frontend: <https://bloodline-avrajsekhon-ui.onrender.com>
  - API documentation: <https://bloodline-avrajsekhon-api.onrender.com/docs>
- Made the one-click demo logins persist: when demo mode is enabled the API adds any missing synthetic demo accounts on every start, and the login page detects demo mode from the API.
- Found that the dashboard stayed blank for more than 90 seconds on the live server because fitting SARIMA is too slow for the free CPU. SARIMA is now off by default in the server image (`BLOODLINE_SARIMA=0`), so the live forecasts compare the 14-day baseline and SES only; SARIMA can still be enabled with `BLOODLINE_SARIMA=1`. The dashboard now loads in about 6 seconds.
- Added a "Waking up the server" message, shown when the free server is starting after a period of inactivity, instead of a blank page.
- Replaced the relative-position bank diagram on the Regional page with an interactive OpenStreetMap map (Leaflet) showing each blood bank and a shortage heatmap that can be filtered by blood group.
- Notifications: kept in-app alerts only (browser push pop-ups were turned off), let donors delete their own alerts, removed the 24-hour repeat limit for demo accounts so outreach can be demonstrated repeatedly, and fixed alert times that were shown 5.5 hours early because the server stores UTC.
- Made the demo data keep at least one matchable donor for every blood group that has demo donors (O+ previously had none because its only donor was within the 90-day cooldown).
- Updated the README to describe the live deployment.

## Testing

Each change was checked with the backend test suite (61 tests passing) and in a headless Chrome browser against a local server, and then checked on the live site.

## Problems and Fixes

- Blank dashboard on the live site: caused by slow SARIMA fitting on the free CPU; fixed by disabling SARIMA by default on the server.
- Wrong notification times: server times are stored in UTC without a time-zone marker; the frontend now treats them as UTC.
- No O+ donors in the demo: the only O+ demo donor was in cooldown; the demo setup now keeps one donor per group available.

## Tools and AI assistance

An AI assistant (Claude) was used to deploy the application, write the changes and tests, and diagnose the issues above. I created and configured the Render services and their environment settings, chose which features to add or remove (map heatmap, demo logins, in-app notifications only), tested the live site in Chrome for each role and reported the problems listed above.

## Outcome

BloodLine is publicly accessible with one-click demo accounts, a faster dashboard, a map-based regional view and simpler in-app notifications.
