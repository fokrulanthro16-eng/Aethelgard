/**
 * Developer Tools — /demo
 *
 * This route is only available in non-production environments.
 * In a production build (NODE_ENV === "production"), Next.js serves a 404.
 *
 * Use this page to:
 *   - Seed a realistic demo scenario (POST /demo/setup)
 *   - View system capability stats (GET /demo/stats)
 *   - Access architecture and judge dashboards
 */
import { notFound } from "next/navigation";
import DemoPageClient from "@/components/demo-page-client";

export default function DemoPage() {
  if (process.env.NODE_ENV === "production") {
    notFound();
  }
  return <DemoPageClient />;
}
