import type { Metadata } from "next";

import { BRAND_DESCRIPTION } from "@/lib/brand";

export const metadata: Metadata = {
  description: BRAND_DESCRIPTION,
};

export default function CreateLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return children;
}
