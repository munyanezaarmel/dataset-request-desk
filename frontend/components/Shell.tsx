"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { api, getToken, Me, setToken } from "@/lib/api";

/** Wraps every logged-in page: checks the session, draws the nav, passes `me` down. */
export default function Shell({ children }: { children: (me: Me) => ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api<Me>("/auth/me").then(setMe).catch(() => router.replace("/login"));
  }, [router]);

  if (!me) return <p className="muted">Loading…</p>;
  const staff = me.role !== "client";

  return (
    <>
      <header>
        <strong>Dataset Request Desk</strong>
        <nav>
          <Link href="/requests">Requests</Link>
          {staff && <Link href="/analytics">Analytics</Link>}
          {staff && <Link href="/import">Import episodes</Link>}
        </nav>
        <span className="spacer" />
        <span className="muted">
          {me.name} ({me.role})
        </span>
        <button
          className="secondary"
          onClick={() => {
            setToken(null);
            router.replace("/login");
          }}
        >
          Log out
        </button>
      </header>
      <main>{children(me)}</main>
    </>
  );
}
