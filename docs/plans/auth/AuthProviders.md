# Auth Provider Options

## Requirements

See [Auth.md](Auth.md).

## Options

Note: we also need to choose an email provider. See [AuthMail.md](AuthMail.md).

### Managed Service: Auth0

Auth0 is third-party hosted IdP service. All properties redirect to Auth0 for login. Auth0 provides a "Universal Login" page that can be themed to match your branding, hosted on a custom domain like `auth.theflip.museum`.

At ~30 users (growing to perhaps a few hundred with public registration), this falls well within Auth0's free tier (25,000 MAU). The free tier includes unlimited social login providers and 1 custom domain.

**Pros:**

- Registration, forgot password, email verification, social login, account linking, rate limiting, and session management all come out of the box
- OIDC client libraries (e.g. Authlib) exist for every framework in our stack
- Custom user metadata (e.g. `is_museum_staff`) supported natively
- OIDC is a standard — if Auth0 ever becomes a problem, you can migrate to another OIDC provider without changing your apps' integration code
- GDPR account deletion and user self-service profile management available
- Supports bulk user import with PBKDF2 password hashes on the free tier. Django's `pbkdf2_sha256$iterations$salt$hash` format would need a conversion script to Auth0's PHC format, but existing Flipfix users could keep their passwords.
- Password hash export is available (requires a support ticket; may not be available on the free tier), which reduces vendor lock-in for password-based users
- Attack protection for signup and login flows is built in
- 1 custom domain on the free tier means we can host login at something like `auth.theflip.museum`

**Cons:**

- **Session lifetime on free tier is short** — max 3-day idle timeout and 30-day absolute session lifetime. A user who doesn't visit for 4 days gets logged out. We want sessions lasting months. Longer sessions require Enterprise pricing (~$30k/year). This is a significant UX concern for a casual wiki-style site like Pinbase.
- **MFA is not available on the free tier.** Essentials plan ($35/mo B2C) gets basic TOTP; Professional ($240/mo) adds SMS/email/push.
- **Custom email templates need more verification** — Auth0 definitely requires an external email provider for production email and branded transactional email, but it is not yet clear from the docs whether template customization itself is gated behind a paid plan.
- Login UI is hosted by Auth0 (customizable, but not fully yours)
- Still requires us to configure an external email provider for production email sending; Auth0's built-in email provider is for testing only
- True OIDC back-channel logout exists, but Auth0 documents it as an Enterprise feature, so we should not count on that for v1
- User data lives on Auth0's servers (US or EU region selectable)

Auth0 also has startup and nonprofit programs, which may matter if we later need paid features.

However, this does not solve the session-lifetime problem. Auth0's public nonprofit discount is 50% off paid plans, which would bring Essentials to about $17.50/mo and Professional to about $120/mo. But the long-session capability appears to require Enterprise, and Enterprise would therefore still cost more than Professional and remain out of budget.

### Managed Service: WorkOS AuthKit

WorkOS AuthKit is a third-party hosted auth platform with hosted login/signup flows, password auth, social login, MFA, email verification, user management, and a branded authentication UI. Free tier covers up to 1 million MAU.

WorkOS sends auth emails itself by default (from `workos-mail.com`), which eliminates the need for a separate email provider — unless we want a custom sending domain.

WorkOS exposes standard OIDC/OAuth2 endpoints, so we can integrate with any OIDC library (`mozilla-django-oidc`, `authlib`, etc.) — not locked into their SDK.

**Pros:**

- Hosted service with no auth infrastructure for us to run
- 1 million MAU on the free tier (vastly more generous than Auth0's 25k)
- Password auth, social login, email verification, forgot password, MFA, and account linking all included on the free tier (Auth0 charges $35/mo for MFA alone)
- WorkOS sends auth emails itself by default — no separate email provider to configure
- Standard OIDC/OAuth2 — not SDK-locked like Clerk; works with any OIDC client library
- Hosted UI supports logo and brand color customization on the free tier
- Session configuration is available on the free tier. In the dashboard we verified:
  - Maximum session length can be set to 365 days
  - Access token duration defaults to 5 minutes and the UI appears to allow much longer values
  - Inactivity timeout defaults to 2 days and we successfully increased it to 100 days
- Supports bulk user import with PBKDF2 password hashes. Django 5.1+ (which the Flipfix system was born on) uses 870,000 iterations, which is within WorkOS's accepted range (600k–1M). Requires a format conversion script from Django's format to PHC format. Import is one API call per user (no bulk endpoint).
- User metadata for custom attributes (e.g. `is_museum_staff`) supported
- If we later decide to bring our own email provider, WorkOS supports SES, Mailgun, Postmark, Resend, and SendGrid

**Cons:**

- **No password hash export** — WorkOS does not allow exporting password hashes. If we migrate away, every password-based user must reset their password. (WorkOS imports hashes willingly but won't give them back.) Social login users are unaffected since their identity is anchored to the external provider.
- **Custom domains (auth UI + email sending) are $99/mo** — a single bundle that covers auth domain, admin portal domain, and email sending domain. Without this, the login UI lives on WorkOS's domain and emails come from `workos-mail.com`.
- **Email customization is limited compared to a full template editor** — WorkOS supports branding assets, brand colors, localized copy, and custom email-provider integrations, but if we need full control over email HTML/text we may still need to disable WorkOS emails and send our own.

If we relax the custom domain requirement, WorkOS's free tier is significantly more capable than Auth0's for our use case — MFA, generous MAU limits, built-in email sending, and long-lived sessions that can be configured up to 365 days.

### Managed Service: Clerk

Clerk is a hosted auth and user-management platform with passwords, social login, automatic account linking, user metadata, hosted UI components, and a free tier that includes a custom domain.

Its pricing is attractive: free for small apps, custom domain included, unlimited applications, and up to 50,000 monthly retained users per app. If this were a pure Next.js or React estate, it would be a stronger contender.

**Pros:**

- Hosted service with no auth infrastructure to run
- Custom domain available on Pro plan ($20–25/mo)
- Unlimited applications on one account
- Password auth, social login, automatic account linking, usernames, and user metadata are all supported
- Device/session management is built in
- Shared auth across subdomains is a first-class Clerk concept
- Clerk can act as an OAuth/OIDC identity provider for external apps
- Self-service password hash export from the dashboard (CSV), no support ticket needed — the most migration-friendly option

**Cons:**

- **OIDC discovery is non-standard** — Clerk publishes `/.well-known/oauth-authorization-server` (RFC 8414), not `/.well-known/openid-configuration` (the OIDC standard). Libraries like `mozilla-django-oidc` and `authlib` expect the latter and won't auto-discover Clerk's endpoints. You'd need to manually configure each endpoint URL.
- **No standard Django integration path** — every Django + Clerk integration in the wild uses Clerk-specific JWT verification, not standard OIDC. Clerk has a Python SDK (`clerk-backend-api`) and a community `clerk-django` package, but both are vendor-specific. There are zero documented examples of anyone using a generic OIDC library with Clerk on Django.
- Clerk is much more SDK- and component-centric than OIDC-centric; its sweet spot is Next.js / React, whereas our estate is a mix of Django, SvelteKit, Next.js, and Python
- MFA, custom email templates, and custom session lifetime are paid features
- Hobby plan session duration is fixed at 7 days; Pro plan max is not documented (practical ceiling is Chrome's 400-day cookie limit)
- Multi-domain and advanced shared-session docs are heavily oriented around Clerk-managed frontend apps, which makes this feel like a less natural fit for Flipfix and Juice than a more conventional OIDC provider

Clerk is interesting on price, but looks less aligned with our mixed-stack, standards-first integration needs than Auth0.

### Rejected Options

#### Managed Service: Amazon Cognito

Rejected because I already know from experience that Cognito is difficult to work with, hard to debug, hard to configure, and I do not want to bring AWS complexity into this project.

#### Managed Service: Descope

Rejected because custom domain support starts at the Pro plan, and Descope Pro starts at `$249/mo`, which is too expensive.

#### Self-Hosted IdP: Authentik

Rejected because I do not want to run an auth service ourselves.

Authentik is a self-hosted identity provider. We'd run it ourselves on Railway alongside our existing services. Authentik is built on Django under the hood, so it's culturally familiar. It provides a full admin UI, OIDC/OAuth2/SAML support, social login, email verification, MFA, and user management.

**Pros:**

- Full control over all auth infrastructure and user data
- No vendor dependency or pricing risk
- Feature-rich: social login, MFA, email verification, forgot password, account linking, user self-service, admin UI
- Built on Django/Python — familiar stack for debugging and customization
- Supports custom attributes for the "museum staff" flag
- No limits on social providers or login customizations
- Can be themed to match your branding completely

**Cons:**

- Another Railway service to host, monitor, update, and back up
- You still need to configure SMTP for transactional email (e.g. Postmark, Mailgun, SES) — email deliverability is your problem
- More moving parts: Authentik needs a database, Redis, and a worker process
- Operational burden on a small team — security patches, version upgrades, etc.
- More initial setup and configuration compared to a managed service

#### Build It Ourselves: django-allauth

Rejected because I do not want to build and own an auth system ourselves.

Create a dedicated Django auth service (or extend Flipfix) using django-allauth, which provides social login, email verification, forgot password, and account management as Django views and forms.

**Pros:**

- Stays entirely within your existing tech stack — it's just Django
- Maximum control and customization over every flow and UI element
- No external dependency or additional service to host (if built into Flipfix)
- django-allauth is mature and widely used
- No vendor costs at any scale

**Cons:**

- Most engineering effort of the three options — you're building auth UI, registration flows, and security hardening yourself
- You still need email infrastructure (SMTP via Postmark, SES, etc.) — deliverability is your problem
- Flipfix remains the IdP, preserving the coupling between a maintenance app and critical identity infrastructure — or you spin up yet another Django service
- Account linking (email + social for same user) requires careful implementation
- MFA, rate limiting, session management, and global logout all need to be built or wired up manually
- Ongoing maintenance burden: security patches, keeping up with OAuth spec changes, social provider API changes

## How they Integrate

Regardless of which option we pick, the integration pattern is the same for each property:

- **Pinbase**: User clicks login → redirect to IdP → authenticate → redirect back → Django creates session. Fits your existing same-origin proxy architecture perfectly.
- **Flipfix**: Switches from being the OAuth provider to being an OAuth client. django-allauth or mozilla-django-oidc on the client side. Existing ~30 users migrated to the new IdP.
- **Juice**: Swaps Flipfix's OAuth endpoint for the new IdP's. Minimal change.
- **www**: No change now. If needed later, NextAuth.js speaks OIDC natively.

### The "Museum Staff" Flag

The requirement for optionally knowing "this person is museum staff" across properties maps cleanly to OIDC claims or user metadata. All three options support this — the IdP stores a custom attribute like is_museum_staff: true, and each property can read it from the token and decide what to do with it locally. It's not complex in any of the options.

## Comparison

Only the three actively considered managed services are compared. ✅ = included on free tier, 💰 = paid, ❌ = not available.

|                                                                         | Auth0             | WorkOS AuthKit    | Clerk                              |
| ----------------------------------------------------------------------- | ----------------- | ----------------- | ---------------------------------- |
| [Standard OIDC/OAuth2](Auth.md#ease-of-integration)                     | ✅                | ✅                | ❌❌❌ SDK-only, no OIDC discovery |
| [Forgot password](Auth.md#forgot-password)                              | ✅                | ✅                | ✅                                 |
| [Email verification](Auth.md#email-verification)                        | ✅                | ✅                | ✅                                 |
| [Social login](Auth.md#social-login)                                    | ✅                | ✅                | ✅                                 |
| [Account linking](Auth.md#email--social-logins-work-seamlessly)         | ✅                | ✅                | ✅                                 |
| [MFA](Auth.md#security)                                                 | 💰 $35/mo         | ✅                | 💰 $20/mo                          |
| [Long-lived sessions](Auth.md#sessions)                                 | 💰 Enterprise     | ✅ up to 365 days | 💰 $20/mo (free = 7 days)          |
| [User metadata / staff flag](Auth.md#museum-staff-identity-across-apps) | ✅                | ✅                | ✅                                 |
| [GDPR account deletion](Auth.md#user-initiated-deleting)                | ✅                | ✅                | ✅                                 |
| [Rate limiting](Auth.md#security)                                       | ✅                | ✅                | ✅                                 |
| [Hosted vendor](Auth.md#dont-build-it-ourselves)                        | ✅                | ✅                | ✅                                 |
| [Cost](Auth.md#cost)                                                    | Free (25k MAU)    | Free (1M MAU)     | Free (50k MAU)                     |
| [Initial user migration](Auth.md#initial-user-migration)                | PBKDF2 import ✅  | PBKDF2 import ✅  | PBKDF2 import ✅                   |
| [Password hash export](Auth.md#ease-of-migrating-off)                   | 💰 support ticket | ❌                | ✅ self-service                    |
| Custom domain                                                           | ✅ (free tier)    | 💰 $99/mo         | 💰 $20/mo                          |
| Built-in email sending                                                  | ❌ testing only   | ✅                | ✅                                 |
| Custom email templates                                                  | unclear           | Limited           | 💰 $20/mo                          |
