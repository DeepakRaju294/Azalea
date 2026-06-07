"use client";

import Link from "next/link";
import { ArrowRight, Clock3 } from "lucide-react";

type RecommendedItem = {
  key: string;
  title: string;
  href: string;
  badge: string;
  minutes?: string | null;
};

type RecommendedNextCardProps = {
  items: RecommendedItem[];
};

export default function RecommendedNextCard({
  items,
}: RecommendedNextCardProps) {
  if (items.length === 0) return null;

  return (
    <div className="flex h-50 flex-col rounded-3xl border border-[#E7E1EF] bg-white/82 p-5 shadow-sm shadow-purple-200/20">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-[#6F6A7D]">
          Recommended next
        </p>

        <span className="rounded-full bg-[#F7F2FF] px-3 py-1 text-[11px] font-semibold text-[#6F46D9]">
          Up next
        </span>
      </div>

      <div className="mt-5 flex flex-1 flex-col justify-end gap-4">
        {items.slice(0, 2).map((item) => (
          <Link
            key={item.key}
            href={item.href}
            className="group flex min-h-12 items-center justify-between gap-4 rounded-2xl px-2 py-1.5 transition hover:bg-[#F3ECFF]"
          >
            <div className="min-w-0">
              <p className="truncate text-base font-bold leading-tight tracking-[-0.01em] text-[#21172F]">
                {item.title}
              </p>

              <div className="mt-1.5 flex items-center gap-2 text-xs leading-none text-[#817A92]">
                <span>{item.badge}</span>

                {item.minutes && (
                  <>
                    <span>•</span>
                    <span className="inline-flex items-center gap-1">
                      <Clock3 className="h-3.5 w-3.5" />
                      {item.minutes}
                    </span>
                  </>
                )}
              </div>
            </div>

            <ArrowRight className="h-4 w-4 shrink-0 text-[#817A92] transition group-hover:translate-x-0.5 group-hover:text-[#6F46D9]" />
          </Link>
        ))}
      </div>
    </div>
  );
}