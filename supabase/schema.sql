-- ============================================================
-- Spupoll Database Schema
-- Run this in Supabase SQL Editor (project: zpikaoimoqpibqdnnlhk)
-- ============================================================

-- ── Admins ────────────────────────────────────────────────────
-- References auth.users so Supabase Auth is the identity layer.
create table if not exists admins (
  id          uuid primary key references auth.users(id) on delete cascade,
  email       text unique not null,
  name        text not null,
  approved    boolean not null default false,
  is_super    boolean not null default false,
  approved_by uuid references admins(id),
  created_at  timestamptz not null default now()
);

-- Auto-create an admins row when a user signs up via Supabase Auth.
create or replace function handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into admins (id, email, name)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'name', split_part(new.email, '@', 1))
  );
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure handle_new_user();

-- Promote the super-admin. Run AFTER Vish creates his account.
-- update admins set approved = true, is_super = true
--   where email = 'viswajeethgk@gmail.com';

-- ── Sessions ──────────────────────────────────────────────────
create table if not exists sessions (
  id         uuid primary key default gen_random_uuid(),
  admin_id   uuid not null references admins(id) on delete cascade,
  title      text not null,
  short_code text unique not null,
  format     text not null check (format in ('standalone', 'pre_post')),
  status     text not null default 'draft'
               check (status in ('draft','pre_open','pre_closed','post_open','complete')),
  created_at timestamptz not null default now()
);

create index if not exists sessions_admin_id_idx  on sessions(admin_id);
create index if not exists sessions_short_code_idx on sessions(short_code);

-- ── Questions ─────────────────────────────────────────────────
create table if not exists questions (
  id          uuid primary key default gen_random_uuid(),
  session_id  uuid not null references sessions(id) on delete cascade,
  order_index integer not null,
  template    text not null check (template in ('scale5','likert','binary','mc','slider')),
  text        text not null,
  options     jsonb,   -- MC: ["Option A","Option B",...]
  anchors     jsonb,   -- scale/slider: {"lo":"Not at all","hi":"Completely"}
  created_at  timestamptz not null default now(),
  unique (session_id, order_index)
);

create index if not exists questions_session_id_idx on questions(session_id);

-- ── Responses ─────────────────────────────────────────────────
-- One row per device × question × phase. The unique constraint
-- ensures participants cannot double-submit.
create table if not exists responses (
  id           uuid primary key default gen_random_uuid(),
  session_id   uuid not null references sessions(id) on delete cascade,
  question_id  uuid not null references questions(id) on delete cascade,
  device_id    text not null,
  phase        text not null check (phase in ('pre','post')),
  value        text not null,   -- numeric string for ordinal; label text for binary/mc
  submitted_at timestamptz not null default now(),
  unique (question_id, device_id, phase)
);

create index if not exists responses_session_id_idx  on responses(session_id);
create index if not exists responses_device_id_idx   on responses(device_id);
create index if not exists responses_question_id_idx on responses(question_id);

-- ── Result Configs ────────────────────────────────────────────
-- Stores the admin's chart selection for each session × phase.
create table if not exists result_configs (
  id         uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(id) on delete cascade,
  admin_id   uuid not null references admins(id) on delete cascade,
  phase      text not null check (phase in ('pre','post')),
  selections jsonb not null,  -- [{question_id, charts:["distribution","sankey",...]}]
  created_at timestamptz not null default now(),
  unique (session_id, admin_id, phase)
);

-- ── Row-Level Security ────────────────────────────────────────
alter table admins        enable row level security;
alter table sessions      enable row level security;
alter table questions     enable row level security;
alter table responses     enable row level security;
alter table result_configs enable row level security;

-- admins: each admin can read their own row
create policy "admins_select_own" on admins
  for select to authenticated
  using (id = auth.uid());

-- sessions: admins full control over their own sessions
create policy "sessions_select_own" on sessions
  for select to authenticated using (admin_id = auth.uid());
create policy "sessions_insert_own" on sessions
  for insert to authenticated with check (admin_id = auth.uid());
create policy "sessions_update_own" on sessions
  for update to authenticated using (admin_id = auth.uid());
create policy "sessions_delete_own" on sessions
  for delete to authenticated using (admin_id = auth.uid());

-- sessions: anon can read non-draft sessions (for participants)
create policy "sessions_anon_select" on sessions
  for select to anon using (status != 'draft');

-- questions: anon and authenticated can read questions of non-draft sessions
create policy "questions_select_all" on questions
  for select using (
    exists (
      select 1 from sessions s
      where s.id = questions.session_id and s.status != 'draft'
    )
  );
create policy "questions_manage_own" on questions
  for all to authenticated
  using (
    exists (
      select 1 from sessions s
      where s.id = questions.session_id and s.admin_id = auth.uid()
    )
  );

-- responses: anon can insert; admins can read their session's responses
create policy "responses_anon_insert" on responses
  for insert to anon with check (true);
create policy "responses_select_own" on responses
  for select to authenticated
  using (
    exists (
      select 1 from sessions s
      where s.id = responses.session_id and s.admin_id = auth.uid()
    )
  );

-- result_configs: admins manage their own
create policy "result_configs_own" on result_configs
  for all to authenticated
  using (admin_id = auth.uid())
  with check (admin_id = auth.uid());
