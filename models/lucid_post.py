from .database import get_db_connection
from tqdm import tqdm


class LucidPost:
    """Model for Lucid Forum posts - stored in separate lucid_posts table"""
    
    def __init__(self, id=None, user_id=None, company_id=None, post_id=None,
                 thread_url=None, thread_title=None, author=None, 
                 timestamp=None, text=None, post_link=None, scraped_at=None):
        self.id = id
        self.user_id = user_id
        self.company_id = company_id
        self.post_id = post_id
        self.thread_url = thread_url
        self.thread_title = thread_title
        self.author = author
        self.timestamp = timestamp
        self.text = text
        self.post_link = post_link
        self.scraped_at = scraped_at

    @staticmethod
    def create_table():
        """Create lucid_posts table if it doesn't exist"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lucid_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                company_id TEXT NOT NULL,
                post_id TEXT NOT NULL,
                thread_url TEXT NOT NULL,
                thread_title TEXT,
                author TEXT,
                timestamp TEXT,
                text TEXT,
                post_link TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, company_id, post_id, thread_url)
            )
        """)
        
        conn.commit()
        conn.close()
        print("✅ lucid_posts table created/verified")

    @staticmethod
    def save_lucid_posts_to_db(thread_link, posts, user_id, company_id):
        """Save Lucid forum posts to separate lucid_posts table"""
        # Ensure table exists
        LucidPost.create_table()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        saved_count = 0
        skipped_count = 0

        print(f"💾 Saving {len(posts)} Lucid posts to database...")
        for p in tqdm(posts, desc="💾 Saving Lucid posts", unit="post", ncols=100):
            post_id = p.get("post_id", "")
            thread_url = p.get("thread_url", thread_link)
            thread_title = p.get("thread_title", thread_link.split('/')[-1].replace('-', ' ').title() if thread_link else "Lucid Forum Thread")
            author = p.get("author", "Anonymous")
            timestamp = p.get("timestamp", "")
            text = p.get("text", "")
            post_link = p.get("post_link", "")

            # Check if post already exists for this user and company
            cur.execute("""
                SELECT COUNT(*) FROM lucid_posts 
                WHERE user_id = ? AND company_id = ? AND post_id = ? AND thread_url = ?
            """, (user_id, company_id, post_id, thread_url))
            
            exists = cur.fetchone()[0] > 0
            
            if exists:
                skipped_count += 1
                continue
            
            try:
                cur.execute("""
                    INSERT INTO lucid_posts 
                    (user_id, company_id, post_id, thread_url, thread_title, author, timestamp, text, post_link)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, 
                    company_id, 
                    post_id, 
                    thread_url,
                    thread_title,
                    author, 
                    timestamp, 
                    text,
                    post_link
                ))
                saved_count += 1
            except Exception as e:
                print(f"⚠️ Error saving post {post_id}: {e}")
                skipped_count += 1
        
        conn.commit()
        conn.close()
        
        return saved_count, skipped_count

    @staticmethod
    def get_posts_by_user(user_id, limit=None):
        """Get all Lucid posts for a user"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = "SELECT * FROM lucid_posts WHERE user_id = ? ORDER BY scraped_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        
        cur.execute(query, (user_id,))
        rows = cur.fetchall()
        conn.close()
        
        posts = []
        for row in rows:
            post = LucidPost(
                id=row[0],
                user_id=row[1],
                company_id=row[2],
                post_id=row[3],
                thread_url=row[4],
                thread_title=row[5],
                author=row[6],
                timestamp=row[7],
                text=row[8],
                post_link=row[9],
                scraped_at=row[10]
            )
            posts.append(post)
        
        return posts

    @staticmethod
    def get_posts_by_company(company_id, limit=None):
        """Get all Lucid posts for a company"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = "SELECT * FROM lucid_posts WHERE company_id = ? ORDER BY scraped_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        
        cur.execute(query, (company_id,))
        rows = cur.fetchall()
        conn.close()
        
        posts = []
        for row in rows:
            post = LucidPost(
                id=row[0],
                user_id=row[1],
                company_id=row[2],
                post_id=row[3],
                thread_url=row[4],
                thread_title=row[5],
                author=row[6],
                timestamp=row[7],
                text=row[8],
                post_link=row[9],
                scraped_at=row[10]
            )
            posts.append(post)
        
        return posts

    @staticmethod
    def search_posts(query, user_id=None, company_id=None, limit=10):
        """Search Lucid posts by text content"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        search_query = f"%{query}%"
        sql = "SELECT * FROM lucid_posts WHERE (text LIKE ? OR thread_title LIKE ? OR author LIKE ?)"
        params = [search_query, search_query, search_query]
        
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        
        if company_id:
            sql += " AND company_id = ?"
            params.append(company_id)
        
        sql += " ORDER BY scraped_at DESC LIMIT ?"
        params.append(limit)
        
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
        
        posts = []
        for row in rows:
            post = LucidPost(
                id=row[0],
                user_id=row[1],
                company_id=row[2],
                post_id=row[3],
                thread_url=row[4],
                thread_title=row[5],
                author=row[6],
                timestamp=row[7],
                text=row[8],
                post_link=row[9],
                scraped_at=row[10]
            )
            posts.append(post)
        
        return posts

    @staticmethod
    def get_statistics(user_id=None, company_id=None):
        """Get statistics about Lucid posts"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        sql = "SELECT COUNT(*) as total_posts, COUNT(DISTINCT thread_url) as total_threads, COUNT(DISTINCT author) as unique_authors FROM lucid_posts"
        params = []
        
        if user_id:
            sql += " WHERE user_id = ?"
            params.append(user_id)
        elif company_id:
            sql += " WHERE company_id = ?"
            params.append(company_id)
        
        cur.execute(sql, params)
        row = cur.fetchone()
        conn.close()
        
        return {
            "total_posts": row[0] if row else 0,
            "total_threads": row[1] if row else 0,
            "unique_authors": row[2] if row else 0
        }
