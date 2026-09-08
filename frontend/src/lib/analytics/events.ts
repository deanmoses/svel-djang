// Typed registry of frontend-emitted analytics events.
//
// Empty by design at the untyped-events skeleton phase — grows as events
// are added in the typed-events frontend plan. Until then, calls to
// `analytics.capture()` won't type-check, which is the intended gate.
//
// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export interface EventRegistry {}

export type EventName = Extract<keyof EventRegistry, string>;
export type EventProperties<E extends EventName> = EventRegistry[E];
