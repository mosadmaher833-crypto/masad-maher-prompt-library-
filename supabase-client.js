// Supabase public client for the Masad Maher Prompt Library.
// Safe for GitHub Pages: this file contains only the publishable key.
// Never put a Supabase secret/service_role key in this file.
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.57.0';

export const SUPABASE_URL = 'https://mgvfwpwkseqvsngzxuzs.supabase.co';
export const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_arnN7xoJtJ8tSJxHnRXZxw_gzZjDf_E';

export const supabase = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true
  }
});

export async function getCurrentUser() {
  const { data, error } = await supabase.auth.getUser();
  if (error) return null;
  return data.user ?? null;
}

export async function getSession() {
  const { data, error } = await supabase.auth.getSession();
  if (error) return null;
  return data.session ?? null;
}
