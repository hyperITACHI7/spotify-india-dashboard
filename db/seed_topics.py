import yaml
from core.db import get_connection

def seed_topics():
    with open('config/taxonomy.yaml', 'r') as f:
        taxonomy = yaml.safe_load(f)
        
    conn = get_connection()
    cursor = conn.cursor()
    
    for category in taxonomy['categories']:
        topic_id = category['id']
        label = category['label']
        keywords = category.get('keywords', [])
        
        cursor.execute(
            """
            INSERT INTO topics (id, label, keywords)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                label = EXCLUDED.label,
                keywords = EXCLUDED.keywords
            """,
            (topic_id, label, keywords)
        )
        
    conn.commit()
    cursor.close()
    conn.close()
    print("Topics seeded successfully.")

if __name__ == '__main__':
    seed_topics()
