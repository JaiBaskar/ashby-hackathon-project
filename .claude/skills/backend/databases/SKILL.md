---
name: databases
description: Designs and implements database schemas, migrations, indexes, and queries — tables, relationships, constraints, data types, transactions, and query performance. Use whenever the user is modeling data, adding or changing a table, writing a migration, writing or fixing SQL or ORM queries, choosing a database, or debugging a slow query, in any language or ORM (Prisma, Drizzle, SQLAlchemy, Django, ActiveRecord, raw SQL), even if they don't say "database" (e.g. "store users' runs", "add a field for X", "this page loads slowly").
---

# Databases

Do the work: produce the schema, migration files, and queries, not just advice. Match the database, ORM, and migration tool the project already uses.

## Step 1: Gather context (before writing anything)

1. Find the database and tooling: look for `schema.prisma`, `drizzle.config.*`, `models.py`, `alembic/`, `migrations/`, `db/schema.rb`, `.sql` files, or connection strings in env examples.
2. If an existing schema exists, read it fully and follow its conventions (ID type, naming, timestamp columns, soft-delete pattern).
3. If there is no database yet and the user hasn't chosen one, default to **PostgreSQL** and say so in one line. Only suggest a document store (MongoDB) or key-value store (Redis) when the data is genuinely schemaless or the use is caching/queues/sessions.
4. List the queries the feature needs (what screens/endpoints read and write). Design the schema around those queries.

## Step 2: Schema rules

**Naming**: `snake_case`, plural table names (`users`, `run_routes`), singular column names, foreign keys named `<table_singular>_id` (`user_id`). Match the project if it differs.

**Keys**
- Every table has a primary key. Default: `bigint generated always as identity`. Use UUID (v7 preferred, sortable) when IDs are exposed publicly, generated client-side, or merged across systems.
- Every relationship has a real foreign key constraint. State `ON DELETE` explicitly: `CASCADE` for owned children (a user's runs), `RESTRICT` for references that must not vanish, `SET NULL` for optional links.

**Columns**
- `NOT NULL` by default; allow NULL only when "unknown/absent" is a meaningful state.
- Every table gets `created_at timestamptz not null default now()`. Every table whose rows can be edited also gets `updated_at timestamptz not null default now()`, kept current by the ORM or a trigger. Pure join tables (rows are only inserted or deleted) skip `updated_at`.
- Types: `timestamptz` (never naive timestamps), `text` over `varchar(n)` in Postgres unless a limit is a real business rule, `numeric(p,s)` or integer cents for money (never float), `boolean` not 0/1 ints, `jsonb` only for truly variable data you won't filter heavily on.
- Enforce rules in the database: `UNIQUE` for natural uniqueness (email), `CHECK` for ranges (`distance_m > 0`), enums via `CHECK (status IN (...))` or a lookup table.

**Structure**
- Normalize to third normal form by default. Many-to-many relationships use a join table with a composite primary key or unique constraint on the pair.
- Denormalize only for a measured read-performance need; write down the reason in the migration comment.

## Step 3: Indexes

- Index every foreign key column (Postgres does not do this automatically). An existing primary key, unique constraint, or composite index whose **first** column is the FK already counts; don't add a duplicate.
- Add indexes for columns used in `WHERE`, `JOIN`, and `ORDER BY` of the queries from Step 1.4. Composite index column order: equality filters first, then range/sort columns.
- Do not add indexes speculatively. Each index slows writes; tie each one to a query.
- Use a partial index for filtered hot paths (`WHERE deleted_at IS NULL`).

## Step 4: Migrations

- All schema changes go through the project's migration tool. Never instruct the user to change a production schema by hand.
- Never edit a migration that has already been applied anywhere shared; write a new one.
- Every migration has a working down/rollback path, or a comment explaining why it is irreversible.
- For tables that may be large or busy, use the safe multi-step pattern:
  1. Add column as nullable (no default rewrite).
  2. Backfill in batches.
  3. Add `NOT NULL` / constraint afterward.
  4. Create indexes with `CREATE INDEX CONCURRENTLY` (Postgres). This fails inside a transaction, and most migration tools wrap each migration in one, so put it in its own migration with the tool's transaction wrapping turned off.
- Renames and drops: add the new column, dual-write, migrate reads, then drop the old one in a later migration.

## Step 5: Queries

- Parameterized queries or the ORM's query builder only. Never build SQL with string concatenation of user input.
- Select only the columns needed; avoid `SELECT *` in application code.
- Avoid N+1: when loading a list plus related rows, use a join or the ORM's eager-loading (`include`, `joinedload`, `prefetch_related`).
- Wrap multi-step writes that must succeed or fail together in a transaction.
- Paginate with keyset pagination (`WHERE (created_at, id) < ($1, $2) ORDER BY created_at DESC, id DESC LIMIT $3`) for feeds and large tables; offset is fine for small admin lists.
- For a slow query: run `EXPLAIN (ANALYZE, BUFFERS)`, look for sequential scans on large tables and row-estimate mismatches, then fix with an index or a rewrite. Show before/after plans when possible.

## Step 6: Produce output

Deliver in this order:
1. **Entity summary**: tables, one line each on what a row represents, and relationships (one-to-many, many-to-many).
2. **Schema** in the project's format (SQL DDL, Prisma schema, SQLAlchemy models, etc.).
3. **Migration file(s)** ready to run, with rollback.
4. **Queries** the feature needs, written in the project's ORM or SQL.
5. **Decisions**: 2–5 bullets on non-obvious choices (ID type, ON DELETE behavior, any denormalization, indexes added and which query each serves).

## Step 7: Check before finishing

- [ ] Every table has a primary key and `created_at`; every editable table has `updated_at`.
- [ ] Every relationship has a foreign key with explicit `ON DELETE`.
- [ ] Every foreign key column is the first column of some index.
- [ ] Every index maps to a named query.
- [ ] Money is not stored as float; times are `timestamptz`.
- [ ] Migration is reversible or marked irreversible with a reason.
- [ ] No query concatenates user input into SQL.
