from .database import get_db_connection
from bs4 import BeautifulSoup
from tqdm import tqdm
import re


class Post:
    def __init__(self, id=None, user_id=None, company_id=None, category=None, 
                 topic_title=None, topic_url=None, post_number=None, 
                 author=None, created_at=None, cooked_text=None, scraped_at=None,
                 complaint_category='none', car_name='none'):
        self.id = id
        self.user_id = user_id
        self.company_id = company_id
        self.category = category
        self.topic_title = topic_title
        self.topic_url = topic_url
        self.post_number = post_number
        self.author = author
        self.created_at = created_at
        self.cooked_text = cooked_text
        self.scraped_at = scraped_at
        self.complaint_category = complaint_category
        self.car_name = car_name

    @staticmethod
    def save_posts_to_db(category_name, topic_title, topic_url, posts, user_id, company_id):
        """Save posts to database"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        saved_count = 0
        skipped_count = 0

        print(f"💾 Saving {len(posts)} posts to database...")
        for p in tqdm(posts, desc="💾 Saving posts", unit="post", ncols=100):
            post_number = p.get("post_number")

            # Check if post already exists for this user and company
            cur.execute("""
                SELECT COUNT(*) FROM posts 
                WHERE post_number = ? AND topic_url = ? AND user_id = ? AND company_id = ?
            """, (post_number, topic_url, user_id, company_id))
            
            exists = cur.fetchone()[0] > 0
            
            if exists:
                skipped_count += 1
                continue
            
            text = p.get("cooked") or ""
            # store raw cooked HTML and also store plain text trimmed
            plain = BeautifulSoup(text, "lxml").get_text(" ", strip=True) if text else ""
            
            # Classification is handled by batch process after save (run_batch_classification)
            # This ensures it works in both Flask and scheduler contexts
            # Posts are saved with 'none' and batch classifier runs afterward
            complaint_category = 'none'

            # Extract car name - set to 'none' (complaint classifier removed)
            car_name = 'none'

            cur.execute("""
                INSERT INTO posts (user_id, company_id, category, topic_title, topic_url, post_number, author, created_at, cooked_text, complaint_category, car_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, company_id, category_name, topic_title, topic_url, post_number, p.get("username"), p.get("created_at"), plain, complaint_category, car_name))
            saved_count += 1
        
        conn.commit()
        conn.close()
        
        return saved_count, skipped_count
    
    @staticmethod
    def save_reddit_posts_to_db(query, posts, user_id, company_id):
        """Save Reddit posts and comments to database"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        saved_posts = 0
        skipped_posts = 0
        saved_comments = 0
        skipped_comments = 0

        print(f"💾 Saving {len(posts)} Reddit posts to database...")
        
        for p in tqdm(posts, desc="💾 Saving Reddit posts", unit="post", ncols=100):
            post_id = p.get("post_id")

            # Check if post already exists for this user and company
            cur.execute("""
                SELECT COUNT(*) FROM posts 
                WHERE post_number = ? AND topic_url = ? AND user_id = ? AND company_id = ?
            """, (post_id, f"reddit_search_{query}", user_id, company_id))
            
            exists = cur.fetchone()[0] > 0
            
            if exists:
                skipped_posts += 1
            else:
                # Combine title and selftext for content
                content_parts = []
                if p.get("title"):
                    content_parts.append(p.get("title"))
                if p.get("selftext"):
                    content_parts.append(p.get("selftext"))
                
                content = " | ".join(content_parts) if content_parts else ""
                
                # Reddit classification: set to 'none' (complaint classifier removed)
                complaint_category = 'none'

                # Car name extraction for Reddit - set to 'none'
                car_name = 'none'
                
                cur.execute("""
                    INSERT INTO posts (user_id, company_id, category, topic_title, topic_url, post_number, author, created_at, cooked_text, complaint_category, car_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, 
                    company_id, 
                    f"Reddit - {query}", 
                    f"Reddit Search: {query}", 
                    f"reddit_search_{query}",
                    post_id, 
                    p.get("author"), 
                    p.get("created_at"), 
                    content,
                    complaint_category,
                    car_name
                ))
                saved_posts += 1
            
            # Save comments if they exist
            comments = p.get("comments", [])
            if comments:
                for comment in comments:
                    comment_id = comment.get("comment_id", "")
                    
                    # Check if comment already exists
                    cur.execute("""
                        SELECT COUNT(*) FROM posts 
                        WHERE post_number = ? AND topic_url = ? AND user_id = ? AND company_id = ?
                    """, (comment_id, f"reddit_comment_{post_id}", user_id, company_id))
                    
                    comment_exists = cur.fetchone()[0] > 0
                    
                    if comment_exists:
                        skipped_comments += 1
                    else:
                        comment_body = comment.get("body", "")

                        # Car name extraction for Reddit comments - set to 'none'
                        car_name = 'none'

                        # Reddit comment classification - set to 'none' (complaint classifier removed)
                        complaint_category = 'none'
                        
                        # Save comment as a separate post entry
                        cur.execute("""
                            INSERT INTO posts (user_id, company_id, category, topic_title, topic_url, post_number, author, created_at, cooked_text, complaint_category, car_name)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            user_id, 
                            company_id, 
                            f"Reddit Comment - {query}", 
                            f"Comment on: {p.get('title', '')[:100]}...", 
                            f"reddit_comment_{post_id}",
                            comment_id, 
                            comment.get("author"), 
                            comment.get("created_at"), 
                            comment.get("body", ""),
                            complaint_category,
                            car_name
                        ))
                        saved_comments += 1
        
        conn.commit()
        conn.close()
        
        return saved_posts + saved_comments, skipped_posts + skipped_comments

    @staticmethod
    def get_posts_by_user(user_id, limit=None):
        """Get posts for a specific user"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = "SELECT * FROM posts WHERE user_id = ? ORDER BY scraped_at DESC"
        params = [user_id]
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        
        posts = []
        for row in rows:
            post = Post(
                id=row['id'], user_id=row['user_id'], company_id=row['company_id'],
                category=row['category'], topic_title=row['topic_title'],
                topic_url=row['topic_url'], post_number=row['post_number'],
                author=row['author'], created_at=row['created_at'],
                cooked_text=row['cooked_text'], scraped_at=row['scraped_at'],
                complaint_category=row['complaint_category'] if 'complaint_category' in row.keys() else 'none',
                car_name=row['car_name'] if 'car_name' in row.keys() else 'none'
            )
            posts.append(post)
        
        return posts

    @staticmethod
    def get_posts_by_company(company_id, limit=None):
        """Get posts for a specific company"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = "SELECT * FROM posts WHERE company_id = ? ORDER BY scraped_at DESC"
        params = [company_id]
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        
        posts = []
        for row in rows:
            post = Post(
                id=row['id'], user_id=row['user_id'], company_id=row['company_id'],
                category=row['category'], topic_title=row['topic_title'],
                topic_url=row['topic_url'], post_number=row['post_number'],
                author=row['author'], created_at=row['created_at'],
                cooked_text=row['cooked_text'], scraped_at=row['scraped_at'],
                complaint_category=row['complaint_category'] if 'complaint_category' in row.keys() else 'none',
                car_name=row['car_name'] if 'car_name' in row.keys() else 'none'
            )
            posts.append(post)
        
        return posts

    @staticmethod
    def search_posts(query, user_id=None, company_id=None, limit=10):
        """Search posts by content"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        sql = """
            SELECT * FROM posts 
            WHERE (LOWER(topic_title) LIKE ? OR LOWER(cooked_text) LIKE ?)
        """
        params = [f"%{query.lower()}%", f"%{query.lower()}%"]
        
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
            post = Post(
                id=row['id'], user_id=row['user_id'], company_id=row['company_id'],
                category=row['category'], topic_title=row['topic_title'],
                topic_url=row['topic_url'], post_number=row['post_number'],
                author=row['author'], created_at=row['created_at'],
                cooked_text=row['cooked_text'], scraped_at=row['scraped_at'],
                complaint_category=row['complaint_category'] if 'complaint_category' in row.keys() else 'none',
                car_name=row['car_name'] if 'car_name' in row.keys() else 'none'
            )
            posts.append(post)
        
        return posts

    @staticmethod
    def get_statistics(user_id=None, company_id=None):
        """Get post statistics"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        where_clause = ""
        params = []
        
        if user_id:
            where_clause = "WHERE user_id = ?"
            params.append(user_id)
        elif company_id:
            where_clause = "WHERE company_id = ?"
            params.append(company_id)
        
        # Total posts
        cur.execute(f"SELECT COUNT(*) FROM posts {where_clause}", params)
        total_posts = cur.fetchone()[0]
        
        # Unique topics
        cur.execute(f"SELECT COUNT(DISTINCT topic_title) FROM posts {where_clause}", params)
        unique_topics = cur.fetchone()[0]
        
        # Unique authors
        cur.execute(f"SELECT COUNT(DISTINCT author) FROM posts {where_clause}", params)
        unique_authors = cur.fetchone()[0]
        
        # Posts by category
        cur.execute(f"SELECT category, COUNT(*) FROM posts {where_clause} GROUP BY category", params)
        by_category = {row[0]: row[1] for row in cur.fetchall()}
        
        conn.close()
        
        return {
            "total_posts": total_posts,
            "unique_topics": unique_topics,
            "unique_authors": unique_authors,
            "by_category": by_category
        }