from .database import get_db_connection
from tqdm import tqdm


class RedditLucidPost:
    """Model for Reddit Lucid posts - stored in separate reddit_lucid_posts table"""
    
    def __init__(self, id=None, user_id=None, company_id=None, post_id=None,
                 subreddit=None, title=None, author=None, 
                 created_at=None, text=None, post_url=None, score=None, 
                 num_comments=None, scraped_at=None):
        self.id = id
        self.user_id = user_id
        self.company_id = company_id
        self.post_id = post_id
        self.subreddit = subreddit
        self.title = title
        self.author = author
        self.created_at = created_at
        self.text = text
        self.post_url = post_url
        self.score = score
        self.num_comments = num_comments
        self.scraped_at = scraped_at

    @staticmethod
    def create_table():
        """Create reddit_lucid_posts table if it doesn't exist"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reddit_lucid_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                company_id TEXT NOT NULL,
                post_id TEXT NOT NULL,
                subreddit TEXT NOT NULL,
                title TEXT,
                author TEXT,
                created_at TEXT,
                text TEXT,
                post_url TEXT,
                score INTEGER DEFAULT 0,
                num_comments INTEGER DEFAULT 0,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, company_id, post_id, subreddit)
            )
        """)
        
        conn.commit()
        conn.close()
        print("✅ reddit_lucid_posts table created/verified")

    @staticmethod
    def save_reddit_lucid_posts_to_db(subreddit, posts, user_id, company_id):
        """Save Reddit Lucid posts to separate reddit_lucid_posts table"""
        # Ensure table exists
        RedditLucidPost.create_table()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        saved_count = 0
        skipped_count = 0

        print(f"💾 Saving {len(posts)} Reddit Lucid posts to database...")
        for p in tqdm(posts, desc="💾 Saving Reddit Lucid posts", unit="post", ncols=100):
            post_id = p.get("post_id", "")
            title = p.get("title", "")
            author = p.get("author", "Anonymous")
            created_at = p.get("created_at", "")
            text = p.get("text", "")
            post_url = p.get("post_url", "")
            score = p.get("score", 0)
            num_comments = p.get("num_comments", 0)

            # Check if post already exists for this user and company
            cur.execute("""
                SELECT COUNT(*) FROM reddit_lucid_posts 
                WHERE user_id = ? AND company_id = ? AND post_id = ? AND subreddit = ?
            """, (user_id, company_id, post_id, subreddit))
            
            exists = cur.fetchone()[0] > 0
            
            if exists:
                skipped_count += 1
                continue
            
            try:
                cur.execute("""
                    INSERT INTO reddit_lucid_posts 
                    (user_id, company_id, post_id, subreddit, title, author, created_at, text, post_url, score, num_comments)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, 
                    company_id, 
                    post_id, 
                    subreddit,
                    title,
                    author, 
                    created_at, 
                    text,
                    post_url,
                    score,
                    num_comments
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
        """Get all Reddit Lucid posts for a user"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = "SELECT * FROM reddit_lucid_posts WHERE user_id = ? ORDER BY scraped_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        
        cur.execute(query, (user_id,))
        rows = cur.fetchall()
        conn.close()
        
        posts = []
        for row in rows:
            post = RedditLucidPost(
                id=row[0],
                user_id=row[1],
                company_id=row[2],
                post_id=row[3],
                subreddit=row[4],
                title=row[5],
                author=row[6],
                created_at=row[7],
                text=row[8],
                post_url=row[9],
                score=row[10],
                num_comments=row[11],
                scraped_at=row[12]
            )
            posts.append(post)
        
        return posts

    @staticmethod
    def get_posts_by_company(company_id, limit=None):
        """Get all Reddit Lucid posts for a company"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = "SELECT * FROM reddit_lucid_posts WHERE company_id = ? ORDER BY scraped_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        
        cur.execute(query, (company_id,))
        rows = cur.fetchall()
        conn.close()
        
        posts = []
        for row in rows:
            post = RedditLucidPost(
                id=row[0],
                user_id=row[1],
                company_id=row[2],
                post_id=row[3],
                subreddit=row[4],
                title=row[5],
                author=row[6],
                created_at=row[7],
                text=row[8],
                post_url=row[9],
                score=row[10],
                num_comments=row[11],
                scraped_at=row[12]
            )
            posts.append(post)
        
        return posts

    @staticmethod
    def search_posts(query, user_id=None, company_id=None, limit=10):
        """Search Reddit Lucid posts by text content"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        search_query = f"%{query}%"
        sql = "SELECT * FROM reddit_lucid_posts WHERE (text LIKE ? OR title LIKE ? OR author LIKE ?)"
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
            post = RedditLucidPost(
                id=row[0],
                user_id=row[1],
                company_id=row[2],
                post_id=row[3],
                subreddit=row[4],
                title=row[5],
                author=row[6],
                created_at=row[7],
                text=row[8],
                post_url=row[9],
                score=row[10],
                num_comments=row[11],
                scraped_at=row[12]
            )
            posts.append(post)
        
        return posts

    @staticmethod
    def get_statistics(user_id=None, company_id=None):
        """Get statistics about Reddit Lucid posts"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        sql = "SELECT COUNT(*) as total_posts, COUNT(DISTINCT subreddit) as total_subreddits, COUNT(DISTINCT author) as unique_authors FROM reddit_lucid_posts"
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
            "total_subreddits": row[1] if row else 0,
            "unique_authors": row[2] if row else 0
        }
