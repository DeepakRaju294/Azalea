"use client";

/**
 * Shared transition helpers for Visual System V2.
 *
 * `useTransitionStyles` remains for older CSS-based renderers.
 * `useMotionTransitionProps` is the Framer Motion path used by migrated
 * renderers. It maps backend Transition objects onto props that can be spread
 * into `motion.g`, `motion.div`, `motion.button`, etc.
 */

import { useMemo } from "react";
import {
  useReducedMotion,
  type MotionProps,
  type Transition as MotionTransition,
} from "framer-motion";
import type { Transition } from "@/lib/visual_v2_types";

export type TransitionStyle = {
  transition: string;
  transform?: string;
  opacity?: number;
};

export type MotionTransitionProps = Pick<
  MotionProps,
  "initial" | "animate" | "exit" | "layout" | "transition"
>;

export function useTransitionStyles(
  transitions: readonly Transition[],
): Record<string, TransitionStyle> {
  return useMemo(() => {
    const out: Record<string, TransitionStyle> = {};
    for (const transition of transitions) {
      const easing = easingToCss(transition.easing);
      const duration = `${Math.max(0, transition.duration_ms)}ms`;
      const delay = `${Math.max(0, transition.delay_ms)}ms`;
      const css = `${propertyForKind(transition.kind)} ${duration} ${easing} ${delay}`;
      const style: TransitionStyle = { transition: css };

      if (transition.kind === "move") {
        const spec = transition.spec as { to?: { x?: number; y?: number } } | undefined;
        if (typeof spec?.to?.x === "number" && typeof spec.to.y === "number") {
          style.transform = `translate(${spec.to.x}px, ${spec.to.y}px)`;
        }
      } else if (transition.kind === "fade_in" || transition.kind === "appear") {
        style.opacity = 1;
      } else if (transition.kind === "fade_out" || transition.kind === "disappear") {
        style.opacity = 0;
      }

      out[transition.target_element_id] = style;
    }
    return out;
  }, [transitions]);
}

export function useMotionTransitionProps(
  transitions: readonly Transition[],
): Record<string, MotionTransitionProps> {
  const prefersReducedMotion = useReducedMotion();

  return useMemo(() => {
    const out: Record<string, MotionTransitionProps> = {};
    for (const transition of transitions) {
      out[transition.target_element_id] = motionPropsForTransition(
        transition,
        Boolean(prefersReducedMotion),
      );
    }
    return out;
  }, [prefersReducedMotion, transitions]);
}

function motionPropsForTransition(
  transition: Transition,
  prefersReducedMotion: boolean,
): MotionTransitionProps {
  const timing: MotionTransition = prefersReducedMotion
    ? { duration: 0 }
    : {
        duration: Math.max(0, transition.duration_ms) / 1000,
        delay: Math.max(0, transition.delay_ms) / 1000,
        ease: easingToMotion(transition.easing),
      };

  switch (transition.kind) {
    case "move": {
      const spec = transition.spec as {
        from?: { x?: number; y?: number };
        to?: { x?: number; y?: number };
      };
      return {
        initial: prefersReducedMotion
          ? undefined
          : {
              x: typeof spec?.from?.x === "number" ? spec.from.x : 0,
              y: typeof spec?.from?.y === "number" ? spec.from.y : 0,
            },
        animate: {
          x: typeof spec?.to?.x === "number" ? spec.to.x : 0,
          y: typeof spec?.to?.y === "number" ? spec.to.y : 0,
        },
        transition: timing,
      };
    }
    case "appear":
    case "fade_in":
      return {
        initial: prefersReducedMotion ? undefined : { opacity: 0, scale: 0.98 },
        animate: { opacity: 1, scale: 1 },
        transition: timing,
      };
    case "disappear":
    case "fade_out":
      return {
        animate: { opacity: 0, scale: 0.98 },
        transition: timing,
      };
    case "highlight_pulse":
      return {
        animate: prefersReducedMotion
          ? { scale: 1 }
          : {
              scale: [1, 1.08, 1],
              filter: ["none", "drop-shadow(0 0 10px #7C4EF0)", "none"],
            },
        transition: timing,
      };
    case "style_change":
      return {
        animate: { scale: 1 },
        transition: timing,
      };
    case "value_change":
      return {
        initial: prefersReducedMotion ? undefined : { opacity: 0.72 },
        animate: { opacity: 1 },
        transition: timing,
      };
    case "swap":
      return {
        layout: true,
        transition: timing,
      };
    case "stagger_group":
    default:
      return { transition: timing };
  }
}

function easingToCss(easing: Transition["easing"]): string {
  switch (easing) {
    case "linear":
      return "linear";
    case "ease":
      return "ease";
    case "ease_in":
      return "ease-in";
    case "ease_out":
      return "ease-out";
    case "spring":
      return "cubic-bezier(0.34, 1.56, 0.64, 1)";
    case "ease_in_out":
    default:
      return "ease-in-out";
  }
}

function easingToMotion(easing: Transition["easing"]) {
  switch (easing) {
    case "linear":
      return "linear";
    case "ease":
    case "ease_in_out":
      return "easeInOut";
    case "ease_in":
      return "easeIn";
    case "ease_out":
      return "easeOut";
    case "spring":
      return [0.34, 1.56, 0.64, 1];
    default:
      return "easeInOut";
  }
}

function propertyForKind(kind: Transition["kind"]): string {
  switch (kind) {
    case "move":
    case "swap":
      return "transform";
    case "fade_in":
    case "fade_out":
    case "appear":
    case "disappear":
      return "opacity";
    case "style_change":
      return "fill, stroke, background-color, color";
    case "value_change":
      return "color, opacity";
    case "highlight_pulse":
      return "box-shadow, transform";
    case "stagger_group":
      return "none";
    default:
      return "all";
  }
}
