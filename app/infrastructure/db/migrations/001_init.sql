PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS chats (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT,
  full_name TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_roles (
  chat_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('foreman','pdo','procurement','manager','viewer')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (chat_id, user_id),
  FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS requests (
  id TEXT PRIMARY KEY,
  request_code TEXT NOT NULL UNIQUE,
  chat_id INTEGER NOT NULL,
  parent_request_id TEXT,
  is_container INTEGER NOT NULL DEFAULT 0,
  foreman_user_id INTEGER,
  object_name TEXT NOT NULL,
  subobject_name TEXT,
  name_from_foreman TEXT,
  nomenclature_1c TEXT,
  code_1c TEXT,
  requested_qty REAL NOT NULL DEFAULT 0,
  unit TEXT NOT NULL DEFAULT 'шт',
  need_by TEXT,
  from_stock_qty REAL NOT NULL DEFAULT 0,
  to_purchase_qty REAL NOT NULL DEFAULT 0,
  received_total_qty REAL NOT NULL DEFAULT 0,
  remaining_qty REAL NOT NULL DEFAULT 0,
  status_code TEXT NOT NULL,
  stage_code TEXT NOT NULL,
  responsible_role TEXT,
  paused_previous_status TEXT,
  paused_previous_stage TEXT,
  paused_previous_role TEXT,
  closed_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
  FOREIGN KEY (parent_request_id) REFERENCES requests(id) ON DELETE SET NULL,
  FOREIGN KEY (foreman_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_requests_chat_status ON requests(chat_id, status_code, created_at);
CREATE INDEX IF NOT EXISTS idx_requests_parent ON requests(parent_request_id);

CREATE TABLE IF NOT EXISTS request_events (
  id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor_user_id INTEGER NOT NULL,
  actor_role TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_request_events_request_created ON request_events(request_id, created_at);

CREATE TABLE IF NOT EXISTS request_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  chat_id INTEGER NOT NULL,
  message_id INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(chat_id, message_id),
  FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
  FOREIGN KEY (event_id) REFERENCES request_events(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS request_attachments (
  id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  event_id TEXT,
  file_id TEXT NOT NULL,
  file_unique_id TEXT,
  attachment_type TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
  FOREIGN KEY (event_id) REFERENCES request_events(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS request_items (
  id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  line_index INTEGER NOT NULL,
  nomenclature_1c TEXT NOT NULL,
  code_1c TEXT NOT NULL,
  requested_qty REAL NOT NULL,
  unit TEXT NOT NULL,
  from_stock_qty REAL NOT NULL,
  to_purchase_qty REAL NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS outbox (
  id TEXT PRIMARY KEY,
  topic TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  retries INTEGER NOT NULL DEFAULT 0,
  next_retry_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  processed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox(status, next_retry_at);

CREATE TABLE IF NOT EXISTS processed_updates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  update_id INTEGER NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
