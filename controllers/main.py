import os
import time

from flask import (flash, jsonify, redirect, render_template, request,
                   send_file, url_for)
from flask_login import current_user, login_required

from controllers.scraping import (collect_all_topics_from_category,
                                  export_reddit_posts_to_files,
                                  export_topic_posts_to_files,
                                  fetch_categories,
                                  fetch_posts_for_topic_via_json,
                                  search_reddit_posts)
from models.database import get_user_data_dir
from models.post import Post


def index():
    """Redirect to chatbot as the main page"""
    return redirect(url_for('chatbot_advanced'))


def download_file():
    """Download file endpoint"""
    path = request.args.get("path")
    if not path or not os.path.exists(path):
        return "File not found", 404
    return send_file(path, as_attachment=True)


def scrape_single_topic():
    """Scrape all PakWheels discussion threads for selected company (supports multiple URLs with complete pipeline)"""

    if request.method != "POST":
        return redirect(url_for('chatbot_advanced'))

    # Get user's company
    user_company = current_user.company_id or 'haval'

    # Get company configuration
    from config import get_company_config
    from utils.logger import server_logger
    from utils.scraped_urls_tracker import (load_scraped_urls,
                                            mark_url_as_scraped)

    try:
        company_config = get_company_config(user_company)
        company_name = company_config.full_name

        # Get all PakWheels URLs for this company
        all_urls = company_config.get_all_pakwheels_urls()
    except Exception as e:
        flash(f"Error getting company configuration: {e}", "error")
        return redirect(url_for('chatbot_advanced'))

    # Validate we have at least one URL
    if not all_urls:
        flash(f"No PakWheels URLs configured for {company_name}. Please check settings.", "error")
        return redirect(url_for('chatbot_advanced'))

    # Use all URLs - post-level deduplication will handle duplicates
    # This allows re-scraping to pick up NEW posts (2025+ filter + DB dedup)
    urls_to_scrape = all_urls
    previously_scraped_count = len(load_scraped_urls(user_company))

    # Get form parameters
    max_posts = int(request.form.get("max_posts", 1000))
    fetch_mode = request.form.get("fetch_mode", "latest")  # "latest" or "oldest"
    min_year = company_config.min_year if hasattr(company_config, 'min_year') else None
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # Validate max_posts
    if max_posts > 10000:
        max_posts = 10000
        if not is_ajax:
            flash("Maximum posts limited to 10,000 for performance reasons.", "warning")

    # Determine if we want descending order (latest first)
    descending = (fetch_mode == "latest")

    flash(f"Scraping {len(urls_to_scrape)} PakWheels URLs for {company_name} (previously scraped: {previously_scraped_count})", "info")
    server_logger.info(f"Starting multi-URL scraping: {len(urls_to_scrape)} URLs to process for {company_name}")

    total_posts_scraped = 0
    total_urls_completed = 0
    failed_urls = []

    # Loop through each URL (post-level dedup handles duplicates)
    for url_index, thread_url in enumerate(urls_to_scrape, 1):
        try:
            server_logger.info(f"[{url_index}/{len(urls_to_scrape)}] Processing URL: {thread_url}")
            flash(f"[{url_index}/{len(urls_to_scrape)}] Scraping: {thread_url[:80]}...", "info")

            start_time = time.time()

            # Fetch posts from the thread
            posts = fetch_posts_for_topic_via_json(
                topic_url=thread_url,
                max_posts=max_posts,
                descending=descending,
                min_year=min_year
            )

            if not posts:
                server_logger.warning(f"No posts found for URL: {thread_url}")
                flash(f"No posts found for URL {url_index}, skipping...", "warning")
                continue

            # Save posts to database
            saved_count, skipped_count = Post.save_posts_to_db(
                category_name=f"{company_name} Discussion",
                topic_title=f"{company_name} Dedicated Discussion Thread {url_index}",
                topic_url=thread_url,
                posts=posts,
                user_id=current_user.id,
                company_id=user_company
            )

            # Export to files
            json_path, csv_path = export_topic_posts_to_files(
                category_slug=user_company,
                topic_title=f"{company_name} Discussion {url_index}",
                topic_url=thread_url,
                posts=posts
            )

            elapsed_time = time.time() - start_time
            server_logger.info(f"[{url_index}/{len(urls_to_scrape)}] Scraped {len(posts)} posts in {elapsed_time:.1f}s")

            # Start complete pipeline (scraping → blocks → enrichment → embeddings → ChromaDB + PKL)
            if len(posts) > 0:
                try:
                    from ai.haval_pipeline import start_haval_pipeline

                    server_logger.info(f"[{url_index}/{len(urls_to_scrape)}] Starting complete pipeline for {thread_url}")
                    flash(f"[{url_index}/{len(urls_to_scrape)}] Running complete pipeline (blocks → enrichment → embeddings → storage)...", "info")

                    # Start pipeline - this handles:
                    # 1. Conversion to conversation blocks
                    # 2. LLM enrichment (classification, sentiment, tags)
                    # 3. Embedding generation
                    # 4. ChromaDB storage
                    # 5. PKL file saving
                    start_haval_pipeline(
                        json_path=json_path,
                        topic_url=thread_url,
                        sources="Pakwheels",
                        company_id=user_company
                    )

                    server_logger.info(f"[{url_index}/{len(urls_to_scrape)}] Pipeline completed successfully")

                    # Mark URL as scraped ONLY after complete pipeline succeeds
                    mark_url_as_scraped(user_company, thread_url)
                    server_logger.info(f"[{url_index}/{len(urls_to_scrape)}] Marked URL as scraped: {thread_url}")

                    total_posts_scraped += len(posts)
                    total_urls_completed += 1

                    flash(f"[{url_index}/{len(urls_to_scrape)}] Completed: {len(posts)} posts processed and stored", "success")

                except Exception as e:
                    server_logger.error(f"[{url_index}/{len(urls_to_scrape)}] Pipeline failed for {thread_url}: {e}")
                    flash(f"[{url_index}/{len(urls_to_scrape)}] Pipeline failed: {str(e)}", "error")
                    failed_urls.append(thread_url)

        except Exception as e:
            server_logger.error(f"[{url_index}/{len(urls_to_scrape)}] Scraping failed for {thread_url}: {e}")
            flash(f"[{url_index}/{len(urls_to_scrape)}] Scraping failed: {str(e)}", "error")
            failed_urls.append(thread_url)

    # Final summary
    flash(f"Multi-URL scraping completed!", "success")
    flash(f"URLs processed: {total_urls_completed}/{len(urls_to_scrape)}", "info")
    flash(f"Total posts: {total_posts_scraped}", "info")
    if failed_urls:
        flash(f"Failed URLs: {len(failed_urls)}", "warning")

    # Return JSON for AJAX requests
    if is_ajax or request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
        return jsonify({
            "success": True,
            "urls_processed": total_urls_completed,
            "urls_total": len(urls_to_scrape),
            "posts_scraped": total_posts_scraped,
            "failed_urls": len(failed_urls),
            "message": "Multi-URL scraping completed"
        })

    return redirect(url_for('chatbot_advanced'))


@login_required
def scrape_manual_url():
    """Scrape a manually entered PakWheels URL with complete pipeline processing"""

    if request.method != "POST":
        return jsonify({"success": False, "error": "Method not allowed"}), 405

    # Get user's company
    user_company = current_user.company_id or 'haval'

    # Get company configuration
    from config import get_company_config
    from utils.logger import server_logger
    from utils.scraped_urls_tracker import is_url_scraped, mark_url_as_scraped
    from utils.url_validator import (normalize_pakwheels_url,
                                     validate_pakwheels_url)

    try:
        company_config = get_company_config(user_company)
        company_name = company_config.full_name
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error getting company configuration: {str(e)}"
        }), 500

    # Get manual URL from form
    manual_url = request.form.get("manual_url", "").strip()

    if not manual_url:
        return jsonify({
            "success": False,
            "error": "Please enter a PakWheels URL"
        }), 400

    # Normalize and validate URL
    manual_url = normalize_pakwheels_url(manual_url)
    is_valid, error_message = validate_pakwheels_url(manual_url)

    if not is_valid:
        return jsonify({
            "success": False,
            "error": error_message,
            "validation_error": True
        }), 400

    # Check if URL was previously scraped (informational only - we still allow re-scraping)
    was_previously_scraped = is_url_scraped(user_company, manual_url)

    # Get scraping parameters
    max_posts = int(request.form.get("max_posts", 1000))
    fetch_mode = request.form.get("fetch_mode", "latest")
    min_year = company_config.min_year if hasattr(company_config, 'min_year') else None

    # Validate max_posts
    if max_posts > 10000:
        max_posts = 10000

    descending = (fetch_mode == "latest")

    rescrape_msg = " (re-scraping for new posts)" if was_previously_scraped else ""
    server_logger.info(f"[Manual URL] Starting scrape for {company_name}: {manual_url}{rescrape_msg}")

    try:
        start_time = time.time()

        # Fetch posts from the manual URL
        posts = fetch_posts_for_topic_via_json(
            topic_url=manual_url,
            max_posts=max_posts,
            descending=descending,
            min_year=min_year
        )

        if not posts:
            server_logger.warning(f"[Manual URL] No posts found: {manual_url}")
            return jsonify({
                "success": False,
                "error": "No posts found at this URL. Please check the URL and try again."
            }), 404

        # Save posts to database
        saved_count, skipped_count = Post.save_posts_to_db(
            category_name=f"{company_name} Manual Scrape",
            topic_title=f"{company_name} Manual URL",
            topic_url=manual_url,
            posts=posts,
            user_id=current_user.id,
            company_id=user_company
        )

        # Export to files
        json_path, csv_path = export_topic_posts_to_files(
            category_slug=user_company,
            topic_title=f"{company_name} Manual",
            topic_url=manual_url,
            posts=posts
        )

        elapsed_time = time.time() - start_time
        server_logger.info(f"[Manual URL] Scraped {len(posts)} posts in {elapsed_time:.1f}s")

        # Start complete pipeline
        if len(posts) > 0:
            try:
                from ai.haval_pipeline import start_haval_pipeline

                server_logger.info(f"[Manual URL] Starting complete pipeline for {manual_url}")

                # Start pipeline - handles blocks → enrichment → embeddings → storage
                start_haval_pipeline(
                    json_path=json_path,
                    topic_url=manual_url,
                    sources="Pakwheels",
                    company_id=user_company
                )

                server_logger.info(f"[Manual URL] Pipeline completed successfully")

                # Mark URL as scraped ONLY after complete pipeline succeeds
                mark_url_as_scraped(user_company, manual_url)
                server_logger.info(f"[Manual URL] Marked URL as scraped: {manual_url}")

                return jsonify({
                    "success": True,
                    "message": f"Successfully scraped and processed {len(posts)} posts ({saved_count} new, {skipped_count} duplicates)",
                    "posts_scraped": len(posts),
                    "posts_saved": saved_count,
                    "posts_skipped": skipped_count,
                    "was_rescrape": was_previously_scraped,
                    "elapsed_time": round(elapsed_time, 1)
                })

            except Exception as e:
                server_logger.error(f"[Manual URL] Pipeline failed for {manual_url}: {e}")
                return jsonify({
                    "success": False,
                    "error": f"Scraping succeeded but pipeline failed: {str(e)}",
                    "partial_success": True
                }), 500

    except Exception as e:
        server_logger.error(f"[Manual URL] Scraping failed for {manual_url}: {e}")
        return jsonify({
            "success": False,
            "error": f"Scraping failed: {str(e)}"
        }), 500


def pipeline_status():
    """Return JSON describing the current pipeline status"""
    try:
        from ai.haval_pipeline import get_pipeline_status
        status = get_pipeline_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "message": "Pipeline status unavailable"
        })


@login_required
def scrape_reddit():
    """Scrape Reddit posts from configured subreddits (multi-URL support)"""

    if request.method != "POST":
        return redirect(url_for('chatbot_advanced'))

    # Get user's company
    user_company = current_user.company_id or 'haval'

    # Get company configuration
    from config import get_company_config
    from utils.logger import server_logger
    from utils.scraped_urls_tracker import (load_scraped_reddit_urls,
                                            mark_reddit_url_as_scraped)

    try:
        company_config = get_company_config(user_company)
        company_name = company_config.full_name

        # Get all Reddit URLs for this company
        all_reddit_urls = company_config.get_all_reddit_urls()
    except Exception as e:
        flash(f"Error getting company configuration: {e}", "error")
        return redirect(url_for('chatbot_advanced'))

    # Get form parameters
    max_posts = int(request.form.get("max_posts", 1000))
    search_query = request.form.get("search_query", f"{company_name} car")
    subreddit = request.form.get("subreddit", "")  # Optional specific subreddit (overrides multi-URL)
    sort_method = request.form.get("sort_method", "relevance")  # relevance, hot, top, new
    time_filter = request.form.get("time_filter", "all")  # all, year, month, week, day
    include_comments = request.form.get("include_comments", "true").lower() == "true"  # Include comments

    # Get min_year from company config for filtering
    min_year = company_config.min_year if hasattr(company_config, 'min_year') else None

    # Check if this is an AJAX request (from JavaScript)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # Validate max_posts
    if max_posts > 10000:
        max_posts = 10000
        if not is_ajax:
            flash("Maximum posts limited to 10,000 for performance reasons.", "warning")

    try:
        start_time = time.time()

        # Determine subreddits to scrape
        subreddits_to_scrape = []

        if subreddit and subreddit.strip():
            # User specified a specific subreddit - use only that
            subreddits_to_scrape = [subreddit.strip()]
        elif all_reddit_urls:
            # Use configured Reddit URLs - extract subreddit names
            import re
            for url in all_reddit_urls:
                match = re.search(r'reddit\.com/r/([a-zA-Z0-9_]+)', url)
                if match:
                    subreddits_to_scrape.append(match.group(1))

        if not subreddits_to_scrape:
            # Fallback to search-based scraping (no specific subreddit)
            subreddits_to_scrape = [None]

        previously_scraped_count = len(load_scraped_reddit_urls(user_company))

        if not is_ajax:
            flash(f"Scraping {len(subreddits_to_scrape)} Reddit sources for {company_name} (previously scraped: {previously_scraped_count})", "info")
            flash(f"Search query: '{search_query}' | Target: {max_posts} posts per source", "info")

        server_logger.info(f"Starting Reddit scraping: {len(subreddits_to_scrape)} subreddits for {company_name}")

        # Aggregate results from all subreddits
        all_posts = []
        total_saved = 0
        total_skipped = 0

        for sub_index, sub in enumerate(subreddits_to_scrape, 1):
            sub_display = f"r/{sub}" if sub else "all Reddit"
            server_logger.info(f"[{sub_index}/{len(subreddits_to_scrape)}] Scraping {sub_display}")

            if not is_ajax:
                flash(f"[{sub_index}/{len(subreddits_to_scrape)}] Scraping {sub_display}...", "info")

            # Search Reddit posts for this subreddit
            posts = search_reddit_posts(
                query=search_query,
                subreddit=sub,
                sort=sort_method,
                time_filter=time_filter,
                max_posts=max_posts,
                delay=0.5,
                include_comments=include_comments,
                min_year=min_year
            )

            if posts:
                all_posts.extend(posts)

                # Save posts to database (dedup happens here)
                saved_count, skipped_count = Post.save_reddit_posts_to_db(
                    query=f"{search_query}_{sub}" if sub else search_query,
                    posts=posts,
                    user_id=current_user.id,
                    company_id=user_company
                )
                total_saved += saved_count
                total_skipped += skipped_count

                server_logger.info(f"[{sub_index}/{len(subreddits_to_scrape)}] {sub_display}: {len(posts)} posts ({saved_count} new, {skipped_count} duplicates)")

                # Mark subreddit URL as scraped
                if sub:
                    mark_reddit_url_as_scraped(user_company, f"https://www.reddit.com/r/{sub}/")

        # Use aggregated posts
        posts = all_posts
        saved_count = total_saved
        skipped_count = total_skipped
        
        if not posts:
            error_msg = f"No Reddit posts found for '{search_query}'"
            if is_ajax:
                return jsonify({
                    "success": False,
                    "error": error_msg,
                    "message": "No posts found"
                })

            flash(f"No Reddit posts found", "error")
            return redirect(url_for('chatbot_advanced'))

        # Count total comments scraped
        total_comments = sum(post.get('total_comments_scraped', 0) for post in posts)
        
        # Export to files with company-specific naming
        json_path, csv_path = export_reddit_posts_to_files(
            query=search_query,
            posts=posts,
            company_id=user_company
        )
        
        elapsed_time = time.time() - start_time

        server_logger.info(f"Reddit scraping completed: {len(posts)} posts fetched, {saved_count} saved, {skipped_count} skipped")
        
        if not is_ajax:
            flash(f"✅ Reddit scraping completed in {elapsed_time:.1f}s", "success")
            flash(f"📊 Found {len(posts)} posts, saved {saved_count} new items, skipped {skipped_count} duplicates", "info")
            if total_comments > 0:
                flash(f"💬 Scraped {total_comments} comments from posts", "info")
            flash(f"📁 Files saved: {os.path.basename(json_path)}, {os.path.basename(csv_path)}", "info")
        
        # Start pipeline processing for the scraped data
        if len(posts) > 0:
            try:
                server_logger.info(f"Attempting to start pipeline for Reddit data with {len(posts)} posts ({saved_count} new, {skipped_count} duplicates)")
                
                from ai.haval_pipeline import start_haval_pipeline

                # Start pipeline with the exported JSON file
                start_haval_pipeline(
                    json_path=json_path,
                    topic_url=f"reddit_search_{search_query}",
                    sources="Reddit",
                    company_id=user_company
                )
                
                if not is_ajax:
                    flash(f"🚀 Started AI pipeline processing for Reddit data", "info")
                    flash(f"📊 Processing {len(posts)} posts - check progress in real-time", "info")
                server_logger.info(f"Pipeline started successfully for Reddit data")
                
            except Exception as e:
                from utils.logger import log_error
                log_error(e, f"Pipeline startup failed for Reddit data")
                if not is_ajax:
                    flash(f"⚠️ Scraping completed but pipeline startup failed: {str(e)}", "warning")
                server_logger.error(f"Pipeline startup error: {str(e)}")
        else:
            server_logger.info(f"No Reddit posts to process - pipeline startup skipped")
        
        # Return JSON for AJAX requests
        if is_ajax:
            return jsonify({
                "success": True,
                "posts_scraped": len(posts),
                "posts_saved": saved_count,
                "posts_skipped": skipped_count,
                "comments_scraped": total_comments,
                "elapsed_time": elapsed_time,
                "search_query": search_query,
                "include_comments": include_comments,
                "message": "Reddit scraping completed successfully"
            })
            
    except Exception as e:
        from utils.logger import log_error
        log_error(e, f"Reddit scraping failed for query: {search_query}")
        
        # Return JSON error for AJAX requests
        if is_ajax:
            return jsonify({
                "success": False,
                "error": str(e),
                "message": "Reddit scraping failed"
            })
        
        flash(f"❌ Error during Reddit scraping: {str(e)}", "error")
        flash("🔧 This could be due to:", "info")
        flash("• Network connectivity issues", "info")
        flash("• Reddit API problems", "info")
        flash("• Invalid search parameters", "info")
        flash("• Rate limiting", "info")
        flash("💡 Please try again later", "info")

    return redirect(url_for('chatbot_advanced'))


# ============================================================================
# LUCID FORUM SCRAPING ROUTES
# ============================================================================

@login_required
def scrape_lucid():
    """Scrape Lucid forum threads (like Reddit - just a data source)"""

    if request.method != "POST":
        return jsonify({"success": False, "error": "Method not allowed"}), 405

    # Get user's company
    user_company = current_user.company_id or 'haval'

    # Get company configuration
    from config import get_company_config
    from utils.logger import server_logger

    try:
        company_config = get_company_config(user_company)
        company_name = company_config.full_name
    except Exception as e:
        server_logger.error(f"[Lucid] Error getting company configuration: {e}")
        return jsonify({
            "success": False,
            "error": f"Error getting company configuration: {str(e)}"
        }), 500

    # Get form parameters
    base_url = request.form.get("base_url", "https://lucidowners.com").strip()
    max_threads = int(request.form.get("max_threads", 10))
    max_posts = int(request.form.get("max_posts", 50))

    # Validate inputs
    if not base_url:
        return jsonify({
            "success": False,
            "error": "Please enter a Lucid forum URL"
        }), 400

    if max_threads < 1 or max_threads > 1000:
        return jsonify({
            "success": False,
            "error": "Max threads must be between 1 and 1,000"
        }), 400

    if max_posts < 10 or max_posts > 10000:
        return jsonify({
            "success": False,
            "error": "Max posts must be between 10 and 10,000"
        }), 400

    server_logger.info(f"[Lucid] Starting scrape for {company_name}: {base_url} ({max_threads} threads, {max_posts} posts/thread)")

    try:
        from controllers.scraping import scrape_lucid_forum, export_lucid_posts_to_files

        start_time = time.time()

        # Scrape using scraping.py functions
        server_logger.info(f"[Lucid] Scraping forum: {base_url}")
        posts = scrape_lucid_forum(base_url=base_url, max_threads=max_threads, max_posts=max_posts)

        if not posts:
            return jsonify({
                "success": False,
                "error": "No posts found to scrape"
            }), 404

        server_logger.info(f"[Lucid] Scraped {len(posts)} posts")

        # Export to files (like Reddit)
        json_path, csv_path = export_lucid_posts_to_files(base_url, posts, company_id=user_company)
        server_logger.info(f"[Lucid] Exported to {json_path} and {csv_path}")

        # Save posts to database
        total_saved = 0
        total_skipped = 0
        
        try:
            from models.lucid_post import LucidPost
            # Group posts by thread for database saving
            threads_by_url = {}
            for post in posts:
                thread_url = post.get('thread_url', base_url)
                if thread_url not in threads_by_url:
                    threads_by_url[thread_url] = []
                threads_by_url[thread_url].append(post)
            
            for thread_url, thread_posts in threads_by_url.items():
                saved, skipped = LucidPost.save_lucid_posts_to_db(
                    thread_link=thread_url,
                    posts=thread_posts,
                    user_id=current_user.id,
                    company_id=user_company
                )
                total_saved += saved
                total_skipped += skipped
                server_logger.info(f"[Lucid] Saved {saved} posts, skipped {skipped} duplicates from {thread_url}")
        except Exception as e:
            server_logger.error(f"[Lucid] Error saving posts to database: {e}")

        elapsed_time = time.time() - start_time

        server_logger.info(f"[Lucid] Scraping completed: {len(posts)} posts ({total_saved} saved, {total_skipped} skipped) in {elapsed_time:.1f}s")

        # Start pipeline processing (like Reddit)
        try:
            server_logger.info(f"[Lucid] Starting pipeline for {len(posts)} posts")
            
            from ai.haval_pipeline import start_haval_pipeline
            
            # Start pipeline with the exported JSON file
            start_haval_pipeline(
                json_path=json_path,
                topic_url=f"lucid_forum_{base_url.split('/')[-1]}",
                sources="Lucid Forum",
                company_id=user_company
            )
            
            server_logger.info(f"[Lucid] Pipeline started successfully")
            
        except Exception as e:
            server_logger.error(f"[Lucid] Pipeline startup error: {e}")
            import traceback
            server_logger.error(f"[Lucid] Traceback: {traceback.format_exc()}")

        return jsonify({
            "success": True,
            "posts_scraped": len(posts),
            "posts_saved": total_saved,
            "posts_skipped": total_skipped,
            "elapsed_time": round(elapsed_time, 1),
            "message": f"Successfully scraped {len(posts)} posts ({total_saved} saved, {total_skipped} duplicates)"
        })

    except Exception as e:
        server_logger.error(f"[Lucid] Scraping failed: {e}")
        import traceback
        server_logger.error(f"[Lucid] Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": f"Scraping failed: {str(e)}"
        }), 500


@login_required
def scrape_lucid_thread():
    """Scrape a single Lucid forum thread (like Reddit - just a data source)"""

    if request.method != "POST":
        return jsonify({"success": False, "error": "Method not allowed"}), 405

    # Get user's company
    user_company = current_user.company_id or 'haval'

    # Get company configuration
    from config import get_company_config
    from utils.logger import server_logger
    from controllers.scraping import fetch_lucid_url, extract_lucid_posts

    try:
        company_config = get_company_config(user_company)
        company_name = company_config.full_name
    except Exception as e:
        server_logger.error(f"[Lucid] Error getting company configuration: {e}")
        return jsonify({
            "success": False,
            "error": f"Error getting company configuration: {str(e)}"
        }), 500

    # Get form parameters
    thread_url = request.form.get("thread_url", "").strip()
    max_posts = int(request.form.get("max_posts", 50))

    # Validate inputs
    if not thread_url:
        return jsonify({
            "success": False,
            "error": "Please enter a Lucid thread URL"
        }), 400

    if not thread_url.startswith("https://lucidowners.com/threads/"):
        return jsonify({
            "success": False,
            "error": "Invalid Lucid thread URL format",
            "validation_error": True
        }), 400

    if max_posts < 10 or max_posts > 10000:
        return jsonify({
            "success": False,
            "error": "Max posts must be between 10 and 10,000"
        }), 400

    server_logger.info(f"[Lucid] Starting thread scrape: {thread_url}")

    try:
        start_time = time.time()

        # Scrape the thread using scraping.py functions
        server_logger.info(f"[Lucid] Scraping thread: {thread_url}")
        html = fetch_lucid_url(thread_url)
        
        if not html:
            return jsonify({
                "success": False,
                "error": "Failed to fetch thread"
            }), 500

        posts = extract_lucid_posts(html, base_url="https://lucidowners.com")

        if not posts:
            return jsonify({
                "success": False,
                "error": "No posts found in this thread"
            }), 404

        # Limit to max_posts
        posts = posts[:max_posts]
        
        # Add thread info to posts
        for post in posts:
            post["thread_url"] = thread_url
            post["thread_title"] = thread_url.split('/')[-1].replace('-', ' ').title()
        
        server_logger.info(f"[Lucid] Scraped {len(posts)} posts from thread")

        # Save posts to database
        total_saved = 0
        total_skipped = 0
        
        try:
            from models.lucid_post import LucidPost
            saved, skipped = LucidPost.save_lucid_posts_to_db(
                thread_link=thread_url,
                posts=posts,
                user_id=current_user.id,
                company_id=user_company
            )
            total_saved = saved
            total_skipped = skipped
            server_logger.info(f"[Lucid] Saved {saved} posts, skipped {skipped} duplicates")
        except Exception as e:
            server_logger.error(f"[Lucid] Error saving posts to database: {e}")

        # Start pipeline processing (like Reddit)
        try:
            server_logger.info(f"[Lucid] Starting pipeline for {len(posts)} posts")
            
            from ai.haval_pipeline import start_haval_pipeline
            from controllers.scraping import export_lucid_posts_to_files
            
            # Export to JSON first
            json_path, csv_path = export_lucid_posts_to_files("https://lucidowners.com", posts, company_id=user_company)
            
            # Start pipeline with the exported JSON file
            start_haval_pipeline(
                json_path=json_path,
                topic_url=f"lucid_thread_{thread_url.split('/')[-1]}",
                sources="Lucid Forum",
                company_id=user_company
            )
            
            server_logger.info(f"[Lucid] Pipeline started successfully")
            
        except Exception as e:
            server_logger.error(f"[Lucid] Pipeline startup error: {e}")
            import traceback
            server_logger.error(f"[Lucid] Traceback: {traceback.format_exc()}")

        elapsed_time = time.time() - start_time

        server_logger.info(f"[Lucid] Thread scraping completed: {len(posts)} posts in {elapsed_time:.1f}s")

        return jsonify({
            "success": True,
            "posts_scraped": len(posts),
            "posts_saved": total_saved,
            "posts_skipped": total_skipped,
            "elapsed_time": round(elapsed_time, 1),
            "message": f"Successfully scraped {len(posts)} posts ({total_saved} saved, {total_skipped} duplicates)"
        })

    except Exception as e:
        server_logger.error(f"[Lucid] Thread scraping failed: {e}")
        import traceback
        server_logger.error(f"[Lucid] Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": f"Scraping failed: {str(e)}"
        }), 500


# ============================================================================
# REDDIT LUCID SCRAPING
# ============================================================================

@login_required
def scrape_reddit_lucid():
    """Scrape Reddit Lucid Motors subreddits (r/lucidmotors and r/LUCID) in a loop"""

    if request.method != "POST":
        return jsonify({"success": False, "error": "Method not allowed"}), 405

    # Get user's company
    user_company = current_user.company_id or 'lucid'

    # Get company configuration
    from config import get_company_config
    from utils.logger import server_logger
    from controllers.scrape_reddit_lucid import scrape_reddit_lucid_loop, export_reddit_lucid_to_json
    from ai.haval_pipeline import start_haval_pipeline

    try:
        company_config = get_company_config(user_company)
        company_name = company_config.full_name
    except Exception as e:
        server_logger.error(f"[Reddit Lucid] Error getting company configuration: {e}")
        return jsonify({
            "success": False,
            "error": f"Error getting company configuration: {str(e)}"
        }), 500

    # Get form parameters
    max_posts = int(request.form.get("max_posts", 100))
    delay_between_subreddits = int(request.form.get("delay", 5))

    # Get Lucid Reddit URLs from company config
    lucid_reddit_urls = company_config.get_all_reddit_urls()
    
    if not lucid_reddit_urls:
        return jsonify({
            "success": False,
            "error": "No Reddit URLs configured for Lucid company"
        }), 400

    server_logger.info(f"[Reddit Lucid] Starting scrape for {company_name}: {len(lucid_reddit_urls)} subreddits")

    try:
        start_time = time.time()

        # Scrape Reddit Lucid subreddits in a loop
        server_logger.info(f"[Reddit Lucid] Scraping subreddits: {lucid_reddit_urls}")
        print(f"[Reddit Lucid] Scraping subreddits: {lucid_reddit_urls}")
        
        scrape_results = scrape_reddit_lucid_loop(
            subreddits=lucid_reddit_urls,
            max_posts_per_subreddit=max_posts,
            delay_between_subreddits=delay_between_subreddits
        )

        server_logger.info(f"[Reddit Lucid] Scraping complete: {scrape_results['total_posts']} posts found, {scrape_results['total_saved']} saved")

        # Export to JSON
        json_path = export_reddit_lucid_to_json(company_id=user_company)
        
        if not json_path:
            return jsonify({
                "success": False,
                "error": "No posts to export"
            }), 404

        # Start pipeline processing
        try:
            server_logger.info(f"[Reddit Lucid] Starting pipeline for {scrape_results['total_saved']} posts")
            
            start_haval_pipeline(
                json_path=json_path,
                topic_url="reddit_lucid_motors",
                sources="Reddit",
                company_id=user_company
            )
            
            server_logger.info(f"[Reddit Lucid] Pipeline started successfully")
            
        except Exception as e:
            server_logger.error(f"[Reddit Lucid] Pipeline startup error: {e}")
            import traceback
            server_logger.error(f"[Reddit Lucid] Traceback: {traceback.format_exc()}")

        elapsed_time = time.time() - start_time

        server_logger.info(f"[Reddit Lucid] Scraping completed in {elapsed_time:.1f}s")

        return jsonify({
            "success": True,
            "posts_scraped": scrape_results['total_posts'],
            "posts_saved": scrape_results['total_saved'],
            "posts_skipped": scrape_results['total_skipped'],
            "subreddits_processed": scrape_results['subreddits_processed'],
            "elapsed_time": round(elapsed_time, 1),
            "message": f"Successfully scraped {scrape_results['total_posts']} posts ({scrape_results['total_saved']} saved, {scrape_results['total_skipped']} duplicates)"
        })

    except Exception as e:
        server_logger.error(f"[Reddit Lucid] Scraping failed: {e}")
        import traceback
        server_logger.error(f"[Reddit Lucid] Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": f"Scraping failed: {str(e)}"
        }), 500


@login_required
def scrape_reddit_lucid_manual():
    """Scrape a single Reddit Lucid post/thread manually"""

    if request.method != "POST":
        return jsonify({"success": False, "error": "Method not allowed"}), 405

    # Get user's company
    user_company = current_user.company_id or 'lucid'

    # Get company configuration
    from config import get_company_config
    from utils.logger import server_logger
    from controllers.scraping import search_reddit_posts
    from models.reddit_lucid_post import RedditLucidPost
    from ai.haval_pipeline import start_haval_pipeline
    import json
    from datetime import datetime

    try:
        company_config = get_company_config(user_company)
        company_name = company_config.full_name
    except Exception as e:
        server_logger.error(f"[Reddit Lucid Manual] Error getting company configuration: {e}")
        return jsonify({
            "success": False,
            "error": f"Error getting company configuration: {str(e)}"
        }), 500

    # Get form parameters
    post_url = request.form.get("post_url", "").strip()
    max_posts = int(request.form.get("max_posts", 50))

    # Validate URL
    if not post_url:
        return jsonify({
            "success": False,
            "validation_error": True,
            "error": "Please enter a Reddit URL"
        }), 400

    # Check if it's a valid Reddit Lucid URL
    if not ("reddit.com/r/lucidmotors" in post_url or "reddit.com/r/LUCID" in post_url):
        return jsonify({
            "success": False,
            "validation_error": True,
            "error": "Invalid Reddit URL. Must be from r/lucidmotors or r/LUCID"
        }), 400

    # Validate posts count
    if max_posts < 1 or max_posts > 1000:
        return jsonify({
            "success": False,
            "validation_error": True,
            "error": "Posts must be between 1 and 1,000"
        }), 400

    server_logger.info(f"[Reddit Lucid Manual] Starting manual scrape for {company_name}: {post_url}")

    try:
        start_time = time.time()

        # Extract subreddit from URL
        if "r/lucidmotors" in post_url:
            subreddit = "lucidmotors"
        elif "r/LUCID" in post_url:
            subreddit = "LUCID"
        else:
            subreddit = "lucidmotors"  # Default

        server_logger.info(f"[Reddit Lucid Manual] Scraping from {subreddit}: {post_url}")
        print(f"[Reddit Lucid Manual] Scraping from {subreddit}: {post_url}")

        # Search for posts from this URL
        posts = search_reddit_posts(
            query="",
            subreddit=subreddit,
            sort="new",
            time_filter="all",
            max_posts=max_posts,
            include_comments=True
        )

        if not posts:
            server_logger.warning(f"[Reddit Lucid Manual] No posts found for {post_url}")
            return jsonify({
                "success": False,
                "error": "No posts found for this URL"
            }), 404

        total_posts_scraped = len(posts)
        server_logger.info(f"[Reddit Lucid Manual] Found {total_posts_scraped} posts")

        # Save to database
        saved, skipped = RedditLucidPost.save_reddit_lucid_posts_to_db(
            subreddit=subreddit,
            posts=posts,
            user_id=1,  # System user
            company_id=user_company
        )

        server_logger.info(f"[Reddit Lucid Manual] Saved {saved} posts, skipped {skipped} duplicates")

        # Export to JSON for pipeline
        json_filename = f"data/reddit_lucid_manual_{user_company}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        posts_data = []
        for post in posts:
            posts_data.append({
                "post_id": post.get("post_id", ""),
                "subreddit": subreddit,
                "title": post.get("title", ""),
                "author": post.get("author", ""),
                "created_at": post.get("created_at", ""),
                "text": post.get("text", ""),
                "post_url": post.get("post_url", ""),
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0)
            })

        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump({
                "subreddit": subreddit,
                "source_url": post_url,
                "total_posts": len(posts_data),
                "exported_at": datetime.now().isoformat(),
                "posts": posts_data
            }, f, indent=2, ensure_ascii=False)

        server_logger.info(f"[Reddit Lucid Manual] Exported to {json_filename}")

        # Start pipeline processing
        try:
            if saved > 0:
                server_logger.info(f"[Reddit Lucid Manual] Starting pipeline for {saved} posts")
                
                start_haval_pipeline(
                    json_path=json_filename,
                    topic_url=f"reddit_lucid_{subreddit}_manual",
                    sources="Reddit",
                    company_id=user_company
                )
                
                server_logger.info(f"[Reddit Lucid Manual] Pipeline started successfully")
        except Exception as e:
            server_logger.error(f"[Reddit Lucid Manual] Pipeline startup error: {e}")
            import traceback
            server_logger.error(f"[Reddit Lucid Manual] Traceback: {traceback.format_exc()}")

        elapsed_time = time.time() - start_time

        server_logger.info(f"[Reddit Lucid Manual] Scraping completed in {elapsed_time:.1f}s")

        return jsonify({
            "success": True,
            "posts_scraped": total_posts_scraped,
            "posts_saved": saved,
            "posts_skipped": skipped,
            "subreddit": subreddit,
            "elapsed_time": round(elapsed_time, 1),
            "message": f"Successfully scraped {total_posts_scraped} posts ({saved} saved, {skipped} duplicates)"
        })

    except Exception as e:
        server_logger.error(f"[Reddit Lucid Manual] Scraping failed: {e}")
        import traceback
        server_logger.error(f"[Reddit Lucid Manual] Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": f"Scraping failed: {str(e)}"
        }), 500
