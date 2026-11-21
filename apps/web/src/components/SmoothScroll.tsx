"use client";

import { ReactLenis } from "lenis/react";

/**
 * Page-wide smooth scrolling (Lenis). `anchors` makes the in-page "#run" links glide too.
 * Lenis honours prefers-reduced-motion by default, so those users get plain native scrolling.
 * Nested scroll areas opt out with `data-lenis-prevent`.
 */
export function SmoothScroll() {
  return <ReactLenis root options={{ lerp: 0.1, autoRaf: true, anchors: true }} />;
}
