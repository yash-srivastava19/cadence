# Work on these.
def sample():
    pass

def add():
    pass

# some kind of adjacency list or something.
import sqlite3

DATABASE_NAME = "cadence_db.sqlite"

def _create_table():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generation_number INTEGER DEFAULT 0,
            parent_id INTEGER,
            program_code TEXT NOT NULL,
            metric REAL,
            FOREIGN KEY (parent_id) REFERENCES programs(id)
        )
    """)
    conn.commit()
    conn.close()

_create_table()  # Initialize the table on import

def sample(generation_number=0):
    """
    Samples a parent program from the specified generation and returns it along with its children.

    Returns:
        tuple: (parent_program, inspirations) where:
            parent_program (tuple): (id, generation_number, parent_id, program_code, metric) or None if no parent found.
            inspirations (list): List of tuples, each representing a child program:
                                 (id, generation_number, parent_id, program_code, metric)
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Fetch a parent program from the specified generation
    cursor.execute("""
        SELECT id, generation_number, parent_id, program_code, metric
        FROM programs
        WHERE generation_number = ?
        ORDER BY RANDOM()
        LIMIT 1
    """, (generation_number,))
    parent_program = cursor.fetchone()

    # Fetch child programs (inspirations) for the selected parent
    if parent_program:
        parent_id = parent_program[0]
        cursor.execute("""
            SELECT id, generation_number, parent_id, program_code, metric
            FROM programs
            WHERE parent_id = ?
        """, (parent_id,))
        inspirations = cursor.fetchall()
    else:
        inspirations = []

    conn.close()
    return parent_program, inspirations

def add(parent_id, program_code, metric, generation_number):
    """
    Adds a new program to the database.

    Args:
        parent_id (int): ID of the parent program (None for initial program).
        program_code (str): The program's code.
        metric (float): The evaluation metric for the program.
        generation_number (int): The generation number of the program.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO programs (generation_number, parent_id, program_code, metric)
        VALUES (?, ?, ?, ?)
    """, (generation_number, parent_id, program_code, metric))

    conn.commit()
    conn.close()

# Example usage (can be removed later)
if __name__ == '__main__':
    # Add an initial program
    add(None, "print('Hello, world!')", 0.5, 0)

    # Sample from generation 0
    parent, children = sample(0)
    print("Parent:", parent)
    print("Children:", children)

    if parent:
        # Add a child program
        add(parent[0], "print('Hello, evolved!')", 0.7, 1)

        # Sample again to see the child
        parent, children = sample(0)
        print("Parent:", parent)
        print("Children:", children)