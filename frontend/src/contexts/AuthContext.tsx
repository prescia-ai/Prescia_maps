import React, { createContext, useContext, useEffect, useState } from 'react';
import type { User as SupabaseUser, Session } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import api, { fetchSubscriptionStatus } from '../api/client';
import type { SubscriptionInfo } from '../types';

interface UserProfile {
  id: string;
  supabase_id: string;
  email: string;
  username: string | null;
  display_name: string | null;
  bio: string | null;
  location: string | null;
  privacy: string;
  created_at: string | null;
  google_email: string | null;
  google_connected_at: string | null;
  google_folder_id: string | null;
  avatar_url: string | null;
  is_admin?: boolean;
  // Subscription summary (from /auth/me)
  subscription_tier?: string;
  subscription_status?: string;
  is_pro?: boolean;
  trial_ends_at?: string | null;
  pin_count?: number;
}

interface AuthContextValue {
  user: SupabaseUser | null;
  profile: UserProfile | null;
  loading: boolean;
  subscription: SubscriptionInfo | null;
  isPro: boolean;
  pinCount: number | null;
  canLogMoreHunts: boolean;
  signUp: (email: string, password: string) => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  refreshSubscription: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SupabaseUser | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchProfile = async (session: Session) => {
    try {
      const { data } = await api.get<UserProfile>('/auth/me', {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      setProfile(data);
    } catch {
      setProfile(null);
    }
  };

  const loadSubscription = async () => {
    try {
      const info = await fetchSubscriptionStatus();
      setSubscription(info);
    } catch {
      setSubscription(null);
    }
  };

  const refreshProfile = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
      await fetchProfile(session);
    }
  };

  const refreshSubscription = async () => {
    await loadSubscription();
  };

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      if (session) {
        Promise.all([fetchProfile(session), loadSubscription()]).finally(() =>
          setLoading(false)
        );
      } else {
        setLoading(false);
      }
    });

    const { data: { subscription: authSub } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      if (session) {
        fetchProfile(session);
        loadSubscription();
      } else {
        setProfile(null);
        setSubscription(null);
      }
    });

    return () => authSub.unsubscribe();
  }, []);

  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({ email, password });
    if (error) throw error;
  };

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    setUser(null);
    setProfile(null);
    setSubscription(null);
  };

  const isPro = subscription?.is_pro ?? profile?.is_pro ?? false;
  const pinCount = profile?.pin_count ?? null;
  const FREE_PIN_LIMIT = 5;
  const canLogMoreHunts = isPro || (pinCount !== null && pinCount < FREE_PIN_LIMIT);

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        loading,
        subscription,
        isPro,
        pinCount,
        canLogMoreHunts,
        signUp,
        signIn,
        signOut,
        refreshProfile,
        refreshSubscription,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
