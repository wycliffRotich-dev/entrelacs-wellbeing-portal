create table organizations (
  id uuid primary key,
  name text not null unique
);

create table teams (
  id uuid primary key,
  organization_id uuid not null references organizations (id),
  name text not null,
  unique (organization_id, name),
  unique (id, organization_id)
);

create table users (
  id uuid primary key,
  organization_id uuid not null references organizations (id),
  team_id uuid,
  email text not null,
  password_hash text not null,
  role text not null check (role in ('EMPLOYEE', 'HR')),
  unique (id, organization_id),
  foreign key (team_id, organization_id) references teams (id, organization_id),
  check ((role = 'EMPLOYEE' and team_id is not null) or (role = 'HR' and team_id is null))
);
create unique index users_email_lower_key on users (lower(email));

create table check_ins (
  id uuid primary key,
  employee_id uuid not null,
  organization_id uuid not null,
  team_id uuid not null,
  connectedness smallint check (connectedness between 0 and 10),
  support smallint check (support between 0 and 10),
  workload smallint check (workload between 0 and 10),
  score numeric(4, 1) check (score between 0 and 100),
  status text not null check (status in ('DRAFT', 'SUBMITTED')),
  created_at timestamptz not null,
  updated_at timestamptz not null,
  submitted_at timestamptz,
  foreign key (employee_id, organization_id) references users (id, organization_id),
  foreign key (team_id, organization_id) references teams (id, organization_id),
  check (
    (status = 'DRAFT' and submitted_at is null and score is null)
    or (
      status = 'SUBMITTED' and submitted_at is not null and score is not null
      and connectedness is not null and support is not null and workload is not null
    )
  )
);
create unique index check_ins_one_draft_per_employee on check_ins (employee_id) where status = 'DRAFT';
create index check_ins_org_submitted_idx on check_ins (organization_id, submitted_at) where status = 'SUBMITTED';

create function forbid_submitted_check_in_change() returns trigger language plpgsql as $$
begin
  raise exception 'submitted check-ins are immutable' using errcode = 'check_violation';
end
$$;
create trigger check_ins_immutable
  before update or delete on check_ins
  for each row when (old.status = 'SUBMITTED')
  execute function forbid_submitted_check_in_change();
