# SSO

This describes the authentication and authorization requirements and strategy for The Flip's web properties.

## Background

The Flip, Chicago's playable pinball musueum, has a growing collection of web properties.

### The Properties

Right now they are:

#### WWW

The public website. So far it's entirely public, no login. Dunno if that will change or not.

- Lives at https://www.theflip.museum/
- Built in Next.js
- Code a https://github.com/The-Flip/www.theflip.museum

#### Flipfix

The web app used to coordinate maintenance. There are public read-only users, museum staff who can make edits, and Django superuser admins. Users are created by a superuser sending out an invite.

- Lives at https://flipfix.theflip.museum/
- Built in Django
- Code at https://github.com/The-Flip/flipfix

#### Pinbase

An interactive, collaborative wiki-style catalog of all pinball machines in existence. It hasn't gone live yet. It will have public read-only access, public user registration, trusted museum staff roles, and Django superuser admin roles.

- Will live at something like https://pinbase.theflip.museum/
- Built in Django on the back end and Sveltekit on the front end
- Code at https://github.com/deanmoses/pinbase/ but it will be moving under the The-Flip's account

#### Juice

An internal app used to monitor and reboot the pinball machines and other electronics in the musem. This is a tiny little internal application only available to the most trusted museum staff.

- Lives at https://juice.theflip.museum/
- Built in Python
- Code at https://github.com/The-Flip/juice

### Railway Hosting

All of these are currently hosted on Railway, which we like well enough, though we don't want to make decisions that lock us in to Railway.

## SSO Via Flipfix

The first property to need authentication was Flipfix. We used the standard Djanog auth model. Now we need a single login to the other properties, so we implemented OAuth SSO on top of Flipfix; it serves as the OAuth provider right now. The Juice gets its identity through that.

We're not locked in to this arrangement; if there's a better SSO system, we would consider migrating. There's maybe 30? users, it'd be a pain but we could do it.

## The Challenge

Now we need authentication and authorization for Pinbase. Since the public can self-register, this involves a new set of requirements.

### Forgot password

Forgot password is a must.

We have not yet built Forgot Password functionality for Flipfix. For one, we haven't hooked up an email server to send the forgot password messages. I know from past experience that it can be difficult to not be classified as junk mail, so I'm skittish. And then customizing the email HTML so that it displays nicely on all browsers is notoriously tricky. We've already had users forget their password, so it'd be nice to have this, but not critical.

### Email verification

Verify that the person registering owns the email address. Otherwise you get spam accounts and people squatting on addresses. This is a must-have.

If we're doing a system where people can also register with phone numbers, we'd need to verify the phone number. But I don't think we are... seems difficult?

### Social Login

Register/login using your Google/Apple/Facebook/etc identity. I'd kind of like this for Flipfix too, but that's a nice to have.

#### Email & social logins work seamlessly

When someone registers with email/password, then later tries to log in with Google using the same email, that should be treated as the same account, and work seamlessly.

They can they still log in with their password.

### Carry over Flipfix identity

Nice to have: if you are already registered with Flipfix, you are already authenticated to Pinbase and your username and full name are carried over.

If someone already has a Flipfix account, is not logged in to the SSO system, then attempts to register on Pinbase with the same email, it says 'account already taken'... just like it would on Flipfix.

### Account deactivation / banning

#### Admin-initiated deleting

If an admin of a property deactivates / bans a user, it only applies to that property. Deactivating a Flipfix staff account does not deactivate that person's Pinbase account.

Each property will have their own way of dealing with the deactivated user's contributions on that property.

Deleting/banning a truly abusive user will take going to each property.

#### User-initiated deleting

We'd like to support GDPR-style "delete my account", but that may not be in scope for v1. Depends on how hard it is.

### Username and display name

Users should have the same username across all properties.

Their display name should flow to each property, it's a nice to have to override that display name on a per-property basis.

### Authorization / Roles

#### Newly registered public user

When a member of the public registers, I imagine each site will put them in their lowest tier of capability.

**Pinbase**. Right now Pinbase has categories for 'registered user', 'staff' (has access to admin) roles, and superuser. Publicly registered users would be assigned the 'registered user' role. It's up to Pinbase what a registered user can do; that's not the scope of this doc.

**Flipfix**. Will NOT allow any escalated privileges for publicly registered users; they will be treated like unregistered guests.

**Juice**. Will NOT allow publicly registered users (or guest access) in any capacity.

**www**. Has no authentication or authorization requirements at this time.

#### Museum staff identity across apps

If someone is staff on Flipfix, I'd like to be able to use that information on Pinbase to give them escalated privileges. But the Pinbase role model has not yet been figured out. I don't believe there should be a staff role that goes across all properties. If this creates a lot of complexity, I'll probably drop this requirement.

#### Role escalation

On Pinbase, a self-registered user can only become more trusted via some sort of admin action. That will be internal to Pinbase, not visible to the SSO system.

#### No shared authorization

Basically, we're saying is that we should have SSO -- one identity -- but not unified permissions. Unless it's somehow easy to flag a user as museum staff, to enable different properties to use that information in different ways.

### Security

- Rate limiting on registration: yes
- CAPTCHA: no
- Password policy: I guess some sort of minimum complexity, I don't feel strongly on this.
- Multi-factor authentication: nice to have, depends on how hard it is

#### Sessions

- **Session Duration**. Ideally sessions last months, unless that's really a security no-no
- **User revocation**. Users seeing and revoking sessions is a nice to have. Probably not for v1.

### Logout

I don't have a strong opinion on how logout needs to work; either one of these is fine:

- Logging out of one app logs you out of all apps.
- Logging out of one app only logs you out of that app.

### Non-functional Requirements

#### Don't build it ourselves

Building a full SSO system sounds complicated; it's not our core competency; it's yet another service to keep running. My bias is to use a vendor for this, unless there's a good reason not to, or maybe unless there's an off-the-shelf system that is SUPER easy to run.

#### Avoid Vendor Lock-in

I'm nervous about picking a vendor and not being able to migrate. Meaning migrate the actual users with their authentication.

#### Cost

We don't want to spend a lot of ongoing money for this. A vendor with a free tier? $5/mo? Hopefully that's the ballpark we're talking about.

The Flip is a registered Non Profit and all the software that SSO would integrate with is open source, if that changes the cost structure that vendors charge.

#### Initial User Migration

How hard is the initial migration of ~30 Flipfix users into the new system?

- It would be great if existing Flipfix users could keep their passwords... but if this means not using a hosted service provider, I'd drop the requirement.
- Some providers have bulk import tools. That's a nice to have.

#### Ease of Migrating Off

How hard would it be to switch providers? Does the provider allow us to download the user data, including password seeds, so that we can upload them to a different system?

#### Ease of integration

How easy is it to wire up each property?

We strongly prefer a provider that exposes standard OIDC/OAuth2 endpoints (including `/.well-known/openid-configuration` discovery) so that each backend can integrate with a generic OIDC library (`mozilla-django-oidc`, `authlib`, etc.) rather than a vendor-specific SDK.

Our architecture is session-based: the frontend redirects to the IdP, the IdP redirects back, and Django creates a server-side session. This is a standard OIDC authorization code flow. A provider that requires its own JavaScript SDK on the frontend — replacing the redirect flow with client-side JWT verification on every API call — would be a poor fit because:

- It changes our auth model from server-side sessions to per-request JWT verification
- It couples the frontend to the vendor (Clerk components, Clerk API calls) instead of a simple redirect
- Every backend (Django, Python) needs vendor-specific token verification code instead of standard OIDC middleware
- It's more integration surface area to get right across a mixed stack (Django, SvelteKit, Next.js, Python)

#### Hosting location

The properties are all hosted in US/East or US/Chicago, I'd prefer a SSO system that has services there, because perf/lantency.

### Non-Requirements

- **Data residency**
- **Uptime**. These are not mission-critical systems.

## The Options

See [AuthProviders.md](AuthProviders.md)

## The Decision

I don't want to run an auth service ourselves:

- I don't want to build it and own that code
- I don't want to occupy us with the ongoing hosting of it

This pushes us to a hosted vendor.

After reviewing the hosted vendors (see [AuthProviders.md](AuthProviders.md)), WorkOS AuthKit is the leading candidate.

The key reason is sessions. We want users to stay signed in for months. Auth0's self-service plans cap sessions at 3 days idle and 30 days absolute, and the longer session limits appear to require Enterprise pricing, which is out of budget even with nonprofit discounts. By contrast, in a real WorkOS AuthKit account we verified that:

- Maximum session length can be set to 365 days
- Inactivity timeout defaults to 2 days and can be increased to at least 100 days
- Access token duration is configurable

WorkOS also remains strong on the other important requirements:

- Hosted vendor, not self-hosted
- Standard OIDC/OAuth2 integration
- Email/password, social login, email verification, forgot password, MFA, and account linking on the free tier
- Built-in auth email sending, so we do not need a separate email provider for v1 unless we want a custom sending domain

The main downside is branding: custom auth and email domains cost $99/mo. At this point, I would rather give up custom domains than long-lived sessions, so that tradeoff appears acceptable.

So the current direction is:

- Choose WorkOS AuthKit as the SSO provider
- Accept WorkOS-hosted auth and email domains for v1
- Revisit custom domains later only if they become important enough to justify the extra cost
