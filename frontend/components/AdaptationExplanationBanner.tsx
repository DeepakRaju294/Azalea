"use client";

import { useState } from "react";

type AdaptationExplanationBannerProps = {
  title?: string;
  message: string;
  details?: string | null;
  defaultOpen?: boolean;
  className?: string;
};

export default function AdaptationExplanationBanner({
  title = "Why this?",
  message,
  details = null,
  defaultOpen = false,
  className = "",
}: AdaptationExplanationBannerProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div
      className={`rounded-2xl border border-primary/20 bg-accent/70 px-4 py-3 text-left text-sm leading-6 text-foreground ${className}`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-primary">
            {title}
          </p>
          <p className="mt-1 font-medium">{message}</p>
        </div>

        {details && (
          <button
            type="button"
            onClick={() => setIsOpen((value) => !value)}
            className="shrink-0 rounded-full border border-primary/20 bg-background/70 px-3 py-1 text-xs font-semibold text-primary transition hover:bg-background"
          >
            {isOpen ? "Hide" : "Why this?"}
          </button>
        )}
      </div>

      {details && isOpen && (
        <p className="mt-3 border-t border-primary/15 pt-3 text-sm leading-6 text-muted-foreground">
          {details}
        </p>
      )}
    </div>
  );
}
