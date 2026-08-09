// jsdom implements `window.scrollTo` but neither `Element.prototype.scrollTo`
// nor `Element.prototype.scrollIntoView` — any component that scrolls a
// specific container or element into view (ChatPage's auto-scroll-to-latest
// and its "scroll an opened citation into view") throws "is not a function"
// under test with no polyfill. A no-op is enough for both: nothing here
// asserts on the resulting scroll position, only that scrolling doesn't
// crash the component.
/* eslint-disable @typescript-eslint/no-empty-function -- deliberate no-op polyfills */
if (!Element.prototype.scrollTo) {
  Element.prototype.scrollTo = function (): void {};
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function (): void {};
}
/* eslint-enable @typescript-eslint/no-empty-function */
