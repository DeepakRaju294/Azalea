"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { supabase } from "@/lib/supabaseClient";

export async function getCurrentSession() {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  return session;
}

export async function getCurrentUserEmail() {
  const session = await getCurrentSession();
  return session?.user?.email ?? null;
}

export async function logout() {
  await supabase.auth.signOut();
}

export function useRequireAuth() {
  const router = useRouter();
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function checkAuth() {
      const session = await getCurrentSession();

      if (!isMounted) return;

      if (!session) {
        router.push("/login");
        return;
      }

      setUserEmail(session.user.email ?? null);
      setIsCheckingAuth(false);
    }

    checkAuth();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!isMounted) return;

      if (!session) {
        setUserEmail(null);
        router.push("/login");
        return;
      }

      setUserEmail(session.user.email ?? null);
      setIsCheckingAuth(false);
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, [router]);

  async function logoutAndRedirect() {
    await logout();
    setUserEmail(null);
    router.push("/login");
    router.refresh();
  }

  return {
    userEmail,
    isCheckingAuth,
    logout: logoutAndRedirect,
  };
}
