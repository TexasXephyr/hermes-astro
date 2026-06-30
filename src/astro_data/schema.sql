-- Astrology Tool — SQLite Schema (Phase 4)
-- All access via parameterized queries in Python layer.

PRAGMA foreign_keys = ON;

-- People
CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    birth_date TEXT NOT NULL,       -- ISO 8601 YYYY-MM-DD
    birth_time TEXT NOT NULL,       -- HH:MM:SS
    timezone TEXT NOT NULL,         -- IANA format, e.g. America/Los_Angeles
    latitude REAL NOT NULL,         -- decimal degrees
    longitude REAL NOT NULL,        -- decimal degrees
    gender TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Events
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    event_date TEXT NOT NULL,       -- ISO 8601 YYYY-MM-DD
    event_time TEXT,                -- HH:MM:SS or NULL
    timezone TEXT,                -- IANA or NULL
    latitude REAL,                  -- or NULL
    longitude REAL,                 -- or NULL
    event_type TEXT DEFAULT 'general',
    person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Charts
CREATE TABLE IF NOT EXISTS charts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_id TEXT UNIQUE NOT NULL,
    person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    person_b_id INTEGER REFERENCES people(id) ON DELETE SET NULL,  -- synastry
    event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
    chart_type TEXT NOT NULL,       -- 'natal', 'transit', 'synastry', 'progressed'
    calc_date TEXT,                 -- ISO 8601 when calculated
    calc_options TEXT,              -- JSON blob
    positions TEXT NOT NULL,        -- JSON: body positions, signs, degrees, houses
    dignities TEXT,                 -- JSON: domicile/exaltation/etc
    aspects TEXT NOT NULL,          -- JSON: inter-body aspects
    rendered_path TEXT,             -- path to SVG file (NULL until GUI)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Interpretations
CREATE TABLE IF NOT EXISTS interpretations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_id INTEGER REFERENCES charts(id) ON DELETE CASCADE,
    section TEXT NOT NULL,          -- 'natal', 'transit', 'synastry'
    sub_section TEXT,               -- e.g. 'Sun in 5th', 'Saturn conjunct Sun'
    content TEXT NOT NULL,
    generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    model TEXT DEFAULT 'rules'      -- 'rules' or 'llm'
);

-- API Keys
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL,         -- bcrypt hash, or PBKDF2 fallback
    name TEXT NOT NULL,             -- human-readable label
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_used TEXT,
    revoked INTEGER DEFAULT 0       -- 0 = active, 1 = revoked
);

-- Atomic Interpretation Corpus
CREATE TABLE IF NOT EXISTS corpus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    atom_key TEXT NOT NULL,
    text TEXT NOT NULL,
    tags TEXT,                      -- JSON array
    source TEXT DEFAULT 'llm',
    model TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain, atom_key)
);
CREATE INDEX IF NOT EXISTS idx_corpus_domain ON corpus(domain);
CREATE INDEX IF NOT EXISTS idx_corpus_key ON corpus(atom_key);
