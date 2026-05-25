// ── Spupoll frontend configuration ────────────────────────────
// These are public-facing values — safe to commit.

const SUPABASE_URL     = "https://zpikaoimoqpibqdnnlhk.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_NxIILKUJ9IqoRwA8BuA13Q_J0E8WV_-";

// FastAPI backend on Render (update once deployed)
const API_BASE = "https://spupoll-api.onrender.com";

// Initialise the Supabase client (imported as global from CDN)
window.supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
