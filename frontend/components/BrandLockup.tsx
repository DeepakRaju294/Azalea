import Image from "next/image";
import Link from "next/link";
import { Cormorant_Garamond } from "next/font/google";

const logoFont = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["700"],
});

type BrandLockupProps = {
  size?: "sm" | "md" | "lg";
  priority?: boolean;
};

const sizes = {
  sm: {
    wrapper: "gap-1.5",
    markBox: "h-10 w-10",
    mark: 34,
    text: "text-[27px]",
  },
  md: {
    wrapper: "gap-1.5",
    markBox: "h-12 w-12",
    mark: 38,
    text: "text-[31px]",
  },
  lg: {
    wrapper: "gap-1",
    markBox: "h-14 w-14",
    mark: 44,
    text: "text-[38px]",
  },
};

export default function BrandLockup({
  size = "md",
  priority = false,
}: BrandLockupProps) {
  const selectedSize = sizes[size];

  return (
    <Link
      href="/"
      aria-label="Go to Azalea home"
      className={`flex items-center ${selectedSize.wrapper}`}
    >
      <div className={`flex shrink-0 items-center justify-center ${selectedSize.markBox}`}>
        <Image
          src="/Logo.png"
          alt="Azalea logo"
          width={selectedSize.mark}
          height={selectedSize.mark}
          priority={priority}
        />
      </div>

      <span
        className={`${logoFont.className} ${selectedSize.text} font-bold leading-none tracking-[-0.055em] text-[#2B164A]`}
      >
        Azalea
      </span>
    </Link>
  );
}
