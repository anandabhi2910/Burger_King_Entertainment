import sqlite3

DB_NAME = 'burger_king.db'

def create_and_populate_db():
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # 1. Create the orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                OrderID TEXT PRIMARY KEY,
                Items TEXT NOT NULL,
                Status TEXT NOT NULL
            )
        ''')

        # 2. Sample data to insert
        orders_data = [
            ('38', '2x Burger, 1x Coke', 'Preparing'),
            ('39', '1x Wings, 1x Fries', 'Ready'),
            ('40', '3x Chicken Nuggets, 2x Soda', 'Pending'),
            ('41', '1x Hamburger, 1x Water', 'Preparing')
        ]

        # 3. Insert data (or replace if OrderID already exists)
        # This is useful if you run the script multiple times
        cursor.executemany('''
            INSERT OR REPLACE INTO orders (OrderID, Items, Status)
            VALUES (?, ?, ?)
        ''', orders_data)

        conn.commit()
        print(f"Database '{DB_NAME}' created and 'orders' table populated successfully.")

    except sqlite3.Error as e:
        print(f"An SQLite error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_and_populate_db()