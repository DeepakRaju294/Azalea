"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, BookOpen, Sparkles } from "lucide-react";

import { getCurrentSession } from "@/lib/auth";
import { supabase } from "@/lib/supabaseClient";
import BrandLockup from "@/components/BrandLockup";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [status, setStatus] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    async function redirectIfLoggedIn() {
      const session = await getCurrentSession();

      if (session) {
        router.replace("/");
      }
    }

    redirectIfLoggedIn();
  }, [router]);

  useEffect(() => {
    if (!status || isLoading) return;

    const timer = window.setTimeout(() => {
      setStatus("");
    }, 4500);

    return () => window.clearTimeout(timer);
  }, [isLoading, status]);

  async function handleLogin(e: FormEvent) {
    e.preventDefault();

    if (!email.trim() || !password.trim()) {
      setStatus("Enter your email and password.");
      return;
    }

    try {
      setIsLoading(true);
      setStatus("");

      const { error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });

      if (error) {
        setStatus(error.message);
        return;
      }

      router.push("/");
      router.refresh();
    } catch (err) {
      console.error(err);
      setStatus("Failed to log in.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleGoogleLogin() {
    try {
      setIsLoading(true);
      setStatus("");

      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/`,
        },
      });

      if (error) {
        setStatus(error.message);
      }
    } catch (err) {
      console.error(err);
      setStatus("Failed to start Google login.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="azalea-page-soft min-h-screen px-5 py-6 text-foreground md:px-8 lg:px-10">
      <div className="mx-auto flex min-h-[calc(100vh-48px)] max-w-6xl flex-col">
        <nav className="mb-8 flex items-center justify-between">
          <Link href="/">
            <BrandLockup size="sm" />
          </Link>

          <Button asChild variant="ghost" size="sm">
            <Link href="/register">Create account</Link>
          </Button>
        </nav>

        <section className="grid flex-1 items-center gap-8 lg:grid-cols-[1fr_440px]">
          <div className="hidden max-w-2xl lg:block">
            <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent text-primary">
              <Sparkles className="h-8 w-8" />
            </div>

            <p className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <BookOpen className="h-4 w-4" />
              Your learning workspace
            </p>

            <h1 className="text-5xl font-semibold tracking-tight">
              Pick up exactly where you left off.
            </h1>

            <p className="mt-5 max-w-xl text-base leading-8 text-muted-foreground">
              Return to your classes, generated lessons, source-grounded
              questions, and adaptive practice without rebuilding your study
              setup.
            </p>
          </div>

          <Card className="azalea-surface-strong rounded-2xl border shadow-sm">
            <CardHeader>
              <CardDescription>Welcome back</CardDescription>
              <CardTitle className="text-3xl font-semibold tracking-tight">
                Log in
              </CardTitle>
              <p className="text-sm leading-6 text-muted-foreground">
                Continue learning from your saved classes, study paths, and
                practice history.
              </p>
            </CardHeader>

            <CardContent>
              {status && (
                <div className="mb-5 rounded-xl border bg-muted/40 px-4 py-3 text-sm font-medium text-foreground">
                  {status}
                </div>
              )}

              <form onSubmit={handleLogin} className="space-y-4">
                <div>
                  <label className="text-sm font-semibold text-foreground">
                    Email
                  </label>
                  <Input
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    type="email"
                    className="mt-2 h-12 rounded-2xl border-border bg-muted/40 px-4"
                    placeholder="you@example.com"
                  />
                </div>

                <div>
                  <label className="text-sm font-semibold text-foreground">
                    Password
                  </label>
                  <Input
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    type="password"
                    className="mt-2 h-12 rounded-2xl border-border bg-muted/40 px-4"
                    placeholder="Enter your password"
                  />
                </div>

                <Button disabled={isLoading} className="h-12 w-full rounded-2xl">
                  {isLoading ? "Logging in..." : "Log in"}
                  {!isLoading && <ArrowRight className="ml-2 h-4 w-4" />}
                </Button>
              </form>

              <Button
                type="button"
                variant="outline"
                onClick={handleGoogleLogin}
                disabled={isLoading}
                className="mt-3 h-12 w-full rounded-2xl"
              >
                Continue with Google
              </Button>

              <p className="mt-6 text-center text-sm text-muted-foreground">
                New to Azalea?{" "}
                <Link href="/register" className="font-semibold text-primary">
                  Create an account
                </Link>
              </p>
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  );
}
