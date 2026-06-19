PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    real_time TEXT DEFAULT "",
    is_admin BOOLEAN NOT NULL DEFAULT (0)
);

CREATE TABLE IF NOT EXISTS TabModels (
    rowid INTEGER PRIMARY KEY,
    name TEXT,
    date INTEGER
);

CREATE TABLE IF NOT EXISTS TabParts (
    rowid INTEGER PRIMARY KEY,
    name TEXT,
    date INTEGER
);

CREATE TABLE IF NOT EXISTS TabProcesses (
    rowid INTEGER PRIMARY KEY,
    name TEXT,
    date INTEGER,
    part_id INTEGER,
    FOREIGN KEY (part_id) REFERENCES TabParts(rowid)
);

CREATE TABLE IF NOT EXISTS Reports (
    name TEXT,
    model TEXT DEFAULT "",
    part TEXT DEFAULT "",
    process TEXT DEFAULT "",
    time_spent INTEGER DEFAULT "",
    report_date INTEGER,
    rowid INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS TabWorks (
    name TEXT,
    model TEXT,
    part TEXT,
    process TEXT,
    time_spent INTEGER DEFAULT (0),
    last_start INTEGER,
    user_id INTEGER,
    rowid INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS Tmp (
    query TEXT DEFAULT "",
    rowid INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS Rates (
    id INTEGER PRIMARY KEY,
    name TEXT,
    rate REAL DEFAULT (0)
);
