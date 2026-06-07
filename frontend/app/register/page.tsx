"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, FileText, Sparkles } from "lucide-react";

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

export default function RegisterPage() {
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

  async function handleRegister(e: FormEvent) {
    e.preventDefault();

    if (!email.trim() || !password.trim()) {
      setStatus("Enter your email and password.");
      return;
    }

    if (password.length < 6) {
      setStatus("Password should be at least 6 characters.");
      return;
    }

    try {
      setIsLoading(true);
      setStatus("");

      const { error } = await supabase.auth.signUp({
        email: email.trim(),
        password,
      });

      if (error) {
        setStatus(error.message);
        return;
      }

      setStatus("Account created. Check your email if confirmation is enabled.");

      router.push("/");
      router.refresh();
    } catch (err) {
      console.error(err);
      setStatus("Failed to create account.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleGoogleSignup() {
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
      setStatus("Failed to start Google signup.");
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
            <Link href="/login">Log in</Link>
          </Button>
        </nav>

        <section className="grid flex-1 items-center gap-8 lg:grid-cols-[1fr_440px]">
          <div className="hidden max-w-2xl lg:block">
            <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent text-primary">
              <Sparkles className="h-8 w-8" />
            </div>

            <p className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <FileText className="h-4 w-4" />
              Build your study system
            </p>

            <h1 className="text-5xl font-semibold tracking-tight">
              Turn materials into lessons and practice.
            </h1>

            <p className="mt-5 max-w-xl text-base leading-8 text-muted-foreground">
              Create classes, upload source material, generate study paths, and
              keep every practice attempt tied to your progress.
            </p>
          </div>

          <Card className="azalea-surface-strong rounded-2xl border shadow-sm">
            <CardHeader>
              <CardDescription>Start learning</CardDescription>
              <CardTitle className="text-3xl font-semibold tracking-tight">
                Create account
              </CardTitle>
              <p className="text-sm leading-6 text-muted-foreground">
                Save your classes, study paths, progress, practice attempts,
                and recommendations.
              </p>
            </CardHeader>

            <CardContent>
              {status && (
                <div className="mb-5 rounded-xl border bg-muted/40 px-4 py-3 text-sm font-medium text-foreground">
                  {status}
                </div>
              )}

              <form onSubmit={handleRegister} className="space-y-4">
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
                    placeholder="At least 6 characters"
                  />
                </div>

                <Button disabled={isLoading} className="h-12 w-full rounded-2xl">
                  {isLoading ? "Creating account..." : "Create account"}
                  {!isLoading && <ArrowRight className="ml-2 h-4 w-4" />}
                </Button>
              </form>

              <Button
                type="button"
                variant="outline"
                onClick={handleGoogleSignup}
                disabled={isLoading}
                className="mt-3 h-12 w-full rounded-2xl"
              >
                Continue with Google
              </Button>

              <p className="mt-6 text-center text-sm text-muted-foreground">
                Already have an account?{" "}
                <Link href="/login" className="font-semibold text-primary">
                  Log in
                </Link>
              </p>
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  );
}
