# Static showcase hosting

The `site/` directory contains the portfolio page, not a live API or dashboard.
It has no JavaScript execution, authentication, database, or email service.

The root `firebase.json` configures Google's Firebase Hosting (not Firebase App
Hosting). It serves static files with restrictive security headers. There are
no Functions, Cloud Run rewrites, or single-page-app fallback. Unknown login/API
paths return the custom 404 rather than successful HTML.

With an authorized Firebase CLI and a hosting project you control:

```bash
firebase deploy --only hosting --project YOUR_PROJECT_ID
```

Use the Firebase Hosting console to associate your custom domain and to redirect
`www` to the apex. Add the exact DNS records supplied by Google to the existing
DNS provider. Do not copy another site's verification values. Wait for Google's
managed TLS certificate before declaring the custom domain live.

Firebase Hosting includes no-cost usage, but a Google project with Cloud Billing
enabled uses the pay-as-you-go Blaze plan and can incur overage charges. A
separate Spark project avoids hosting overage charges; reaching its quota can
make the site unavailable. Domain registration is separate. Review current
[Google pricing](https://firebase.google.com/pricing) before choosing a project.

This configuration does not deploy the archived application, change its
database, or restart its former Cloud Run services. No auto-deployment workflow
or privileged CI token is included.
