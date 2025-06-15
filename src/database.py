import sqlite3

DATABASE_NAME = "cadence_db.sqlite"

def _create_tables():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Table for storing input instances (e.g., TSP city seeds)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seed INTEGER NOT NULL
        )
    """)

    # Table for storing program versions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            instance_id INTEGER,
            generation_number INTEGER,
            program_code TEXT NOT NULL,
            metric REAL,
            diff TEXT,
            prompt TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES programs(id),
            FOREIGN KEY (instance_id) REFERENCES instances(id)
        )
    """)

    conn.commit()
    conn.close()

_create_tables()

def add_instance(seed: int) -> int:
    """
    Adds a TSP instance seed to the instances table.

    Returns:
        int: ID of the created instance.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("INSERT INTO instances (seed) VALUES (?)", (seed,))
    instance_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return instance_id

def add(program_code: str, metric: float, parent_id: int = None, instance_id: int = None,
        diff: str = None, prompt: str = None) -> int:
    """
    Adds a new program version to the database.

    Args:
        program_code (str): Source code of the program.
        metric (float): Evaluation score.
        parent_id (int, optional): ID of parent program.
        instance_id (int, optional): ID of TSP instance (seed).
        diff (str, optional): Code diff applied to parent.
        prompt (str, optional): Prompt used for generation.

    Returns:
        int: ID of the inserted program.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Compute generation number
    if parent_id is not None:
        cursor.execute("SELECT generation_number FROM programs WHERE id = ?", (parent_id,))
        parent_gen = cursor.fetchone()
        generation_number = parent_gen[0] + 1 if parent_gen else 0
    else:
        generation_number = 0

    cursor.execute("""
        INSERT INTO programs (parent_id, instance_id, generation_number,
                              program_code, metric, diff, prompt)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (parent_id, instance_id, generation_number, program_code, metric, diff, prompt))

    program_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return program_id

def sample(generation_number: int = 0):
    """
    Samples a parent program from a given generation and returns it with its children.

    Returns:
        tuple:
            - parent_program: (id, generation_number, parent_id, program_code, metric, instance_id)
            - inspirations: list of similar tuples (child programs)
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, generation_number, parent_id, program_code, metric, instance_id
        FROM programs
        WHERE generation_number = ?
        ORDER BY RANDOM()
        LIMIT 1
    """, (generation_number,))
    parent_program = cursor.fetchone()

    if parent_program:
        parent_id = parent_program[0]
        cursor.execute("""
            SELECT id, generation_number, parent_id, program_code, metric, instance_id
            FROM programs
            WHERE parent_id = ?
        """, (parent_id,))
        inspirations = cursor.fetchall()
    else:
        inspirations = []

    conn.close()
    return parent_program, inspirations

def get_seed_for_instance(instance_id: int) -> int:
    """
    Fetch the seed value for a given instance.

    Args:
        instance_id (int): Instance row ID.

    Returns:
        int: Seed used to generate the cities.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT seed FROM instances WHERE id = ?", (instance_id,))
    row = cursor.fetchone()

    conn.close()
    return row[0] if row else None

def get_best_program(generation_limit: int = None):
    """
    Fetches the best program (lowest metric) from the database.
    If generation_limit is provided, only considers programs up to that generation.

    Returns:
        tuple: (id, generation_number, parent_id, program_code, metric)
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    if generation_limit is not None:
        cursor.execute("""
            SELECT id, generation_number, parent_id, program_code, metric
            FROM programs
            WHERE generation_number <= ?
            ORDER BY metric ASC
            LIMIT 1
        """, (generation_limit,))
    else:
        cursor.execute("""
            SELECT id, generation_number, parent_id, program_code, metric
            FROM programs
            ORDER BY metric ASC
            LIMIT 1
        """)
    result = cursor.fetchone()
    conn.close()
    return result


# Optional: testing usage
if __name__ == '__main__':
    # Add a test instance (e.g. TSP seed 42)
    instance_id = add_instance(seed=42)

    # Add base program
    program_id = add(
        program_code="""
### START_BLOCK
def tsp(cities):
    return list(range(len(cities)))
### END_BLOCK
""",
        metric=999.9,
        instance_id=instance_id
    )

    # Sample it back
    parent, children = sample(0)
    print("Sampled Parent:", parent)
    print("Children:", children)
