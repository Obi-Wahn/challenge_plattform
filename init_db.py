import sqlite3
from config import DATABASE

def init_db():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    # Teams
    cur.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)

    # Challenges
    cur.execute("""
    CREATE TABLE IF NOT EXISTS challenges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        start_time TEXT,
        end_time TEXT,
        active INTEGER DEFAULT 0
    )
    """)

    # Tasks
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        challenge_id INTEGER,
        title TEXT NOT NULL,
        description TEXT,
        max_points INTEGER,
        FOREIGN KEY (challenge_id) REFERENCES challenges(id)
    )
    """)

    # Submissions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER,
        task_id INTEGER,
        filename TEXT,
        timestamp TEXT,
        points INTEGER,
        comment TEXT,
        UNIQUE(team_id, task_id),
        FOREIGN KEY (team_id) REFERENCES teams(id),
        FOREIGN KEY (task_id) REFERENCES tasks(id)
    )
    """)

    conn.commit()
    conn.close()
    print("Datenbank initialisiert.")

if __name__ == "__main__":
    init_db()
