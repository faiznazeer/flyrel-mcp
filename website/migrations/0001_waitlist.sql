CREATE TABLE waitlist (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    broker_ids TEXT NOT NULL CHECK (json_valid(broker_ids)),
    other_broker TEXT NOT NULL DEFAULT '',
    consent_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
