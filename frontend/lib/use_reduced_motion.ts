"use client";

/**
 * useReducedMotion — reflects the OS-level `prefers-reduced-motion` setting.
 *
 * Returns true when the user prefers reduced motion. Components use this
 * to skip JS-driven animations (Framer Motion, manual setTimeout sequences).
 * For CSS transitions, prefer Tailwind's `motion-safe:` variant — it's
 * automatic and doesn't need this hook.
 *
 * Server-side render returns false (no media-query knowledge).
 */

import { useEffect, useState } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) {
      return;
    }
    const mq = window.matchMedia(QUERY);
    const update = () => setReduced(mq.matches);
    update();
    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", update);
      return () => mq.removeEventListener("change", update);
    }
    // Older Safari
    mq.addListener(update);
    return () => mq.removeListener(update);
  }, []);

  return reduced;
}
