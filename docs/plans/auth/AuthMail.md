# SSO Mail Provider

This describes the mail provider requirements for authentication emails for The Flip's web properties.

## Background

The Flip, Chicago's playable pinball musueum, is implementing SSO across all its web properties. See [Auth.md](Auth.md).

Some hosted auth providers require a separate email provider for production auth mail. Others can send the auth emails themselves. WorkOS AuthKit, for example, can send auth emails by default from a WorkOS domain, which may let us avoid choosing a separate email provider for v1.

## Requirements

### Deliverability

I know from past experience that it can be difficult to not be classified as junk mail, so I'm skittish.

### Reliability

Reliable transactional deliverability for low-volume auth mail

### Email customization

#### Custom Text

We should be able to change the text of the emails.

#### Branding

The emails must be branded with The Flip's branding.

#### Portability

Generating an email such that it displays nicely on all browsers is notoriously tricky. The email provider should somehow make this easy for us.

We don't need a rich email authoring experience.

### Cost

Ideally, somewhere between free and $5/mo. But we'll go higher if it makes our life easier.

### Custom Domain

We want the emails coming from a The Flip domain, something like `authmail.the-flip.museum`.

### Ease

We're looking to minimize hassle. Email is not our core competencey.

#### Hosted Provider

We don't want to host an email server ourselves, we want a hosted provider.

#### Works Well With Selected Auth Provider

It would be great to find one that has super easy integration with our [Auth.md](Auth.md) provider.

#### Easy DNS setup

Hopefully, DNS configuration and domain verification is not too tortuous.

## Non-Requirements

- We do not need a general marketing/newsletter platform

## Options

### Mailgun

### Sendgrid

### Postmark

### Resend

### Amazon Simple Email Service (AWS SES)

Cons:

- We're not in the AWS ecosystem. I don't want to be in the AWS ecosystem because it's difficult to work with.

## Current Direction

For v1, the simplest path is probably to let WorkOS AuthKit send the auth emails itself.

That means:

- No separate email provider to configure for launch
- Less operational hassle
- Verification, password reset, and other auth emails work out of the box

The downside is that the emails would come from a WorkOS domain rather than a The Flip domain.

So the current tradeoff is:

- Easiest v1: let WorkOS send auth emails from its own domain
- More branded future option: later add a separate email provider or paid WorkOS custom email domain support if custom sender branding becomes important enough
