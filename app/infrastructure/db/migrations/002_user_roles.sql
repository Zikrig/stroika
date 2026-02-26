CREATE TABLE IF NOT EXISTS user_roles (
  user_id INTEGER PRIMARY KEY,
  role TEXT NOT NULL CHECK (role IN ('foreman','pdo','procurement','manager','viewer')),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
