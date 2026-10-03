"""
Scheduled Job Wrappers

Wrapper functions for each scheduled job (PakWheels, Reddit, WATI).
Each wrapper:
- Checks pipeline status to avoid conflicts
- Calls existing scraping functions
- Tracks execution history
- Handles errors gracefully
"""

from utils.logger import LoggerManager
from scheduler import job_history
import time
import re

logger = LoggerManager.get_logger('scheduler')


def scrape_pakwheels_job(job_config, job_id):
    """
    Scheduled PakWheels scraping job.

    Scrapes all configured PakWheels URLs for the company,
    saves to database, and runs through AI pipeline.

    Args:
        job_config (dict): Job configuration from YAML
        job_id (str): Job identifier

    Returns:
        dict: Execution result
    """
    company_id = job_config.get('company_id', 'haval')
    parameters = job_config.get('parameters', {})

    # Start tracking
    execution_id = job_history.start_execution(job_id, company_id)

    try:
        # Check pipeline status
        from ai.haval_pipeline import get_pipeline_status
        status = get_pipeline_status()

        if status.get('status') in ('processing', 'enriching', 'indexing'):
            logger.warning(f"[{job_id}] Pipeline busy ({status.get('status')}), skipping scheduled execution")
            if execution_id:
                job_history.mark_skipped(execution_id, f"Pipeline busy: {status.get('status')}")
            return {'success': False, 'skipped': True, 'reason': 'Pipeline busy'}

        # Get company configuration
        from config.companies import get_company_config
        company_config = get_company_config(company_id)

        if not company_config:
            raise ValueError(f"Company configuration not found for '{company_id}'")

        # Get all configured PakWheels URLs
        urls = company_config.get_all_pakwheels_urls()

        if not urls:
            logger.warning(f"[{job_id}] No PakWheels URLs configured for company '{company_id}'")
            if execution_id:
                job_history.mark_skipped(execution_id, "No URLs configured")
            return {'success': False, 'skipped': True, 'reason': 'No URLs configured'}

        logger.info(f"[{job_id}] Scraping {len(urls)} PakWheels URLs for {company_id}")

        # Import scraping functions
        from controllers.scraping import fetch_posts_for_topic_via_json, export_topic_posts_to_files
        from models.post import Post
        from ai.haval_pipeline import start_haval_pipeline
        from utils.scraped_urls_tracker import mark_url_as_scraped

        # Get parameters
        max_posts = parameters.get('max_posts', 1000)
        
        # Ensure max_posts is an integer
        try:
            max_posts = int(max_posts)
        except (ValueError, TypeError):
            logger.warning(f"[{job_id}] Invalid max_posts value: {max_posts}, using default: 1000")
            max_posts = 1000
        
        fetch_mode = parameters.get('fetch_mode', 'latest')
        min_year = company_config.min_year if hasattr(company_config, 'min_year') else None
        descending = (fetch_mode == 'latest')

        total_posts_scraped = 0
        total_posts_saved = 0
        urls_completed = 0

        # Scrape each URL
        for url_index, url in enumerate(urls, 1):
            try:
                logger.info(f"[{job_id}] [{url_index}/{len(urls)}] Scraping URL: {url}")

                # Fetch posts
                posts = fetch_posts_for_topic_via_json(
                    topic_url=url,
                    max_posts=max_posts,
                    descending=descending,
                    min_year=min_year
                )

                if not posts:
                    logger.info(f"[{job_id}] [{url_index}/{len(urls)}] No posts found")
                    continue

                total_posts_scraped += len(posts)
                logger.info(f"[{job_id}] [{url_index}/{len(urls)}] Fetched {len(posts)} posts")

                # Save to database (includes deduplication)
                saved_count, skipped_count = Post.save_posts_to_db(
                    category_name=f"{company_config.full_name} Discussion",
                    topic_title=f"{company_config.full_name} Automated Scrape {url_index}",
                    topic_url=url,
                    posts=posts,
                    user_id=1,  # System user
                    company_id=company_id
                )

                total_posts_saved += saved_count
                logger.info(f"[{job_id}] [{url_index}/{len(urls)}] Saved {saved_count}, skipped {skipped_count} duplicates")

                # Export to files
                json_path, csv_path = export_topic_posts_to_files(
                    category_slug=company_id,
                    topic_title=f"{company_config.full_name} Automated {url_index}",
                    topic_url=url,
                    posts=posts
                )

                logger.info(f"[{job_id}] [{url_index}/{len(urls)}] Exported to {json_path}")

                # Run AI pipeline (if posts were saved)
                if saved_count > 0:
                    logger.info(f"[{job_id}] [{url_index}/{len(urls)}] Starting AI pipeline")
                    start_haval_pipeline(
                        json_path=json_path,
                        topic_url=url,
                        sources="Pakwheels",
                        company_id=company_id
                    )

                # Mark URL as scraped
                mark_url_as_scraped(company_id, url)
                urls_completed += 1

                # Small delay between URLs
                if url_index < len(urls):
                    time.sleep(2)

            except Exception as e:
                logger.error(f"[{job_id}] [{url_index}/{len(urls)}] Error scraping {url}: {e}", exc_info=True)
                # Continue with next URL

        # Mark as successful
        message = f"Scraped {len(urls)} URLs: {total_posts_scraped} posts found, {total_posts_saved} saved"
        logger.info(f"[{job_id}] Completed: {message}")

        if execution_id:
            job_history.mark_success(execution_id, message, records=total_posts_saved)
            # Don't fail the whole job if classification fails

        return {
            'success': True,
            'posts_scraped': total_posts_scraped,
            'posts_saved': total_posts_saved,
            'urls_scraped': urls_completed
        }

    except Exception as e:
        logger.error(f"[{job_id}] Job failed: {e}", exc_info=True)
        if execution_id:
            job_history.mark_failed(execution_id, str(e))
        return {'success': False, 'error': str(e)}


def scrape_reddit_job(job_config, job_id):
    """
    Scheduled Reddit scraping job.

    Scrapes configured Reddit subreddits/URLs for the company.

    Args:
        job_config (dict): Job configuration from YAML
        job_id (str): Job identifier

    Returns:
        dict: Execution result
    """
    company_id = job_config.get('company_id', 'haval')
    parameters = job_config.get('parameters', {})

    # Start tracking
    execution_id = job_history.start_execution(job_id, company_id)

    try:
        # Check pipeline status
        from ai.haval_pipeline import get_pipeline_status
        status = get_pipeline_status()

        if status.get('status') in ('processing', 'enriching', 'indexing'):
            logger.warning(f"[{job_id}] Pipeline busy ({status.get('status')}), skipping scheduled execution")
            if execution_id:
                job_history.mark_skipped(execution_id, f"Pipeline busy: {status.get('status')}")
            return {'success': False, 'skipped': True, 'reason': 'Pipeline busy'}

        # Get company configuration
        from config.companies import get_company_config
        company_config = get_company_config(company_id)

        if not company_config:
            raise ValueError(f"Company configuration not found for '{company_id}'")

        # Get all configured Reddit URLs
        reddit_urls = company_config.get_all_reddit_urls()

        if not reddit_urls:
            logger.warning(f"[{job_id}] No Reddit URLs configured for company '{company_id}'")
            if execution_id:
                job_history.mark_skipped(execution_id, "No Reddit URLs configured")
            return {'success': False, 'skipped': True, 'reason': 'No Reddit URLs configured'}

        # Extract subreddits from URLs
        subreddits = []
        for url in reddit_urls:
            match = re.search(r'reddit\.com/r/([a-zA-Z0-9_]+)', url)
            if match:
                subreddits.append(match.group(1))
            elif url.startswith('r/'):
                subreddits.append(url[2:])

        if not subreddits:
            logger.warning(f"[{job_id}] Could not extract subreddits from URLs")
            if execution_id:
                job_history.mark_skipped(execution_id, "No valid subreddits found")
            return {'success': False, 'skipped': True, 'reason': 'No valid subreddits'}

        logger.info(f"[{job_id}] Scraping {len(subreddits)} Reddit subreddits for {company_id}")

        # Import scraping functions
        from controllers.scraping import search_reddit_posts, export_reddit_posts_to_files
        from models.post import Post
        from ai.haval_pipeline import start_haval_pipeline
        from utils.scraped_urls_tracker import mark_reddit_url_as_scraped

        # Get parameters
        max_posts = parameters.get('max_posts', 1000)
        
        # Ensure max_posts is an integer
        try:
            max_posts = int(max_posts)
        except (ValueError, TypeError):
            logger.warning(f"[{job_id}] Invalid max_posts value: {max_posts}, using default: 1000")
            max_posts = 1000
        
        include_comments = parameters.get('include_comments', True)
        search_query = parameters.get('search_query', f"{company_config.name} car")
        min_year = company_config.min_year if hasattr(company_config, 'min_year') else None

        total_posts_scraped = 0
        total_posts_saved = 0
        subs_completed = 0
        all_posts = []

        # Scrape each subreddit
        for sub_index, subreddit in enumerate(subreddits, 1):
            try:
                logger.info(f"[{job_id}] [{sub_index}/{len(subreddits)}] Scraping r/{subreddit}")

                # Scrape posts
                posts = search_reddit_posts(
                    query=search_query,
                    subreddit=subreddit,
                    sort="relevance",
                    time_filter="all",
                    max_posts=max_posts,
                    delay=0.5,
                    include_comments=include_comments,
                    min_year=min_year
                )

                if not posts:
                    logger.info(f"[{job_id}] [{sub_index}/{len(subreddits)}] No posts found in r/{subreddit}")
                    continue

                all_posts.extend(posts)
                total_posts_scraped += len(posts)
                logger.info(f"[{job_id}] [{sub_index}/{len(subreddits)}] Fetched {len(posts)} posts")

                # Save to database
                saved_count, skipped_count = Post.save_reddit_posts_to_db(
                    query=f"{search_query}_{subreddit}",
                    posts=posts,
                    user_id=1,  # System user
                    company_id=company_id
                )

                total_posts_saved += saved_count
                logger.info(f"[{job_id}] [{sub_index}/{len(subreddits)}] Saved {saved_count}, skipped {skipped_count} duplicates")

                # Mark subreddit as scraped
                mark_reddit_url_as_scraped(company_id, f"https://www.reddit.com/r/{subreddit}/")
                subs_completed += 1

                # Delay between subreddits
                if sub_index < len(subreddits):
                    time.sleep(5)

            except Exception as e:
                logger.error(f"[{job_id}] [{sub_index}/{len(subreddits)}] Error scraping r/{subreddit}: {e}", exc_info=True)

        # Export all posts to files
        if all_posts:
            try:
                json_path, csv_path = export_reddit_posts_to_files(
                    query=f"{company_id}_automated",
                    posts=all_posts,
                    company_id=company_id
                )
                logger.info(f"[{job_id}] Exported {len(all_posts)} posts to {json_path}")

                # Run AI pipeline
                if total_posts_saved > 0:
                    logger.info(f"[{job_id}] Starting AI pipeline")
                    start_haval_pipeline(
                        json_path=json_path,
                        topic_url=f"reddit_scheduled_{company_id}",
                        sources="Reddit",
                        company_id=company_id
                    )
            except Exception as e:
                logger.error(f"[{job_id}] Error in export/pipeline: {e}", exc_info=True)

        # Mark as successful
        message = f"Scraped {len(subreddits)} subreddits: {total_posts_scraped} posts found, {total_posts_saved} saved"
        logger.info(f"[{job_id}] Completed: {message}")

        if execution_id:
            job_history.mark_success(execution_id, message, records=total_posts_saved)

        return {
            'success': True,
            'posts_scraped': total_posts_scraped,
            'posts_saved': total_posts_saved,
            'subreddits_scraped': subs_completed
        }

    except Exception as e:
        logger.error(f"[{job_id}] Job failed: {e}", exc_info=True)
        if execution_id:
            job_history.mark_failed(execution_id, str(e))
        return {'success': False, 'error': str(e)}


def import_wati_job(job_config, job_id):
    """
    Scheduled WATI/WhatsApp import job.

    Fetches messages from WATI API and imports to database.
    The existing fetch_and_import_wati_data function handles
    everything including pipeline start.

    Args:
        job_config (dict): Job configuration from YAML
        job_id (str): Job identifier

    Returns:
        dict: Execution result
    """
    company_id = job_config.get('company_id', 'haval')
    parameters = job_config.get('parameters', {})

    # Start tracking
    execution_id = job_history.start_execution(job_id, company_id)

    try:
        # Check pipeline status with timeout to avoid blocking
        logger.info(f"[{job_id}] Checking pipeline status...")
        
        pipeline_status = None
        status_error = None
        
        def check_status():
            nonlocal pipeline_status, status_error
            try:
                from ai.haval_pipeline import get_pipeline_status
                pipeline_status = get_pipeline_status()
            except Exception as e:
                status_error = str(e)
        
        # Run status check in a thread with timeout
        import threading
        status_thread = threading.Thread(target=check_status, daemon=True)
        status_thread.start()
        status_thread.join(timeout=5)  # 5 second timeout
        
        if status_thread.is_alive():
            logger.warning(f"[{job_id}] Pipeline status check timed out (took >5s), proceeding anyway")
        elif status_error:
            logger.warning(f"[{job_id}] Could not check pipeline status: {status_error}, proceeding anyway")
        elif pipeline_status and pipeline_status.get('status') in ('processing', 'enriching', 'indexing'):
            logger.warning(f"[{job_id}] Pipeline busy ({pipeline_status.get('status')}), skipping scheduled execution")
            if execution_id:
                job_history.mark_skipped(execution_id, f"Pipeline busy: {pipeline_status.get('status')}")
            return {'success': False, 'skipped': True, 'reason': 'Pipeline busy'}

        logger.info(f"[{job_id}] Fetching WATI data for {company_id}")

        # Import WATI function
        from controllers.wati_integration import fetch_and_import_wati_data

        # Get time period
        time_period = parameters.get('time_period', '24h')

        # Fetch and import (this function handles everything)
        result = fetch_and_import_wati_data(
            company_id=company_id,
            time_period=time_period
        )

        if not result.get('success'):
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"[{job_id}] WATI import failed: {error_msg}")
            if execution_id:
                job_history.mark_failed(execution_id, error_msg)
            return {'success': False, 'error': error_msg}

        imported_count = result.get('messages_imported', 0)
        skipped_count = result.get('messages_skipped', 0)
        contacts_count = result.get('contacts_fetched', 0)

        message = f"Imported {imported_count} messages from {contacts_count} contacts ({time_period})"
        logger.info(f"[{job_id}] Completed: {message}")

        if execution_id:
            job_history.mark_success(execution_id, message, records=imported_count)

        return {
            'success': True,
            'records_imported': imported_count,
            'records_skipped': skipped_count,
            'contacts_fetched': contacts_count
        }

    except Exception as e:
        logger.error(f"[{job_id}] Job failed: {e}", exc_info=True)
        if execution_id:
            job_history.mark_failed(execution_id, str(e))
        return {'success': False, 'error': str(e)}


def scrape_lucid_job(job_config, job_id):
    """
    Scheduled Lucid Forum scraping job.

    Scrapes Lucid forum threads for the company.

    Args:
        job_config (dict): Job configuration from YAML
        job_id (str): Job identifier

    Returns:
        dict: Execution result
    """
    company_id = job_config.get('company_id', 'haval')
    parameters = job_config.get('parameters', {})

    # Start tracking
    execution_id = job_history.start_execution(job_id, company_id)

    try:
        # Check pipeline status
        from ai.haval_pipeline import get_pipeline_status
        status = get_pipeline_status()

        if status.get('status') in ('processing', 'enriching', 'indexing'):
            logger.warning(f"[{job_id}] Pipeline busy ({status.get('status')}), skipping scheduled execution")
            if execution_id:
                job_history.mark_skipped(execution_id, f"Pipeline busy: {status.get('status')}")
            return {'success': False, 'skipped': True, 'reason': 'Pipeline busy'}

        # Get company configuration
        from config.companies import get_company_config
        company_config = get_company_config(company_id)

        if not company_config:
            raise ValueError(f"Company configuration not found for '{company_id}'")

        # Check if Lucid is enabled for this company
        if not getattr(company_config, 'has_lucid', False):
            logger.warning(f"[{job_id}] Lucid Forum not enabled for company '{company_id}'")
            if execution_id:
                job_history.mark_skipped(execution_id, "Lucid Forum not enabled")
            return {'success': False, 'skipped': True, 'reason': 'Lucid Forum not enabled'}

        # Get Lucid URL
        lucid_url = getattr(company_config, 'lucid_url', 'https://lucidowners.com')

        if not lucid_url:
            logger.warning(f"[{job_id}] No Lucid URL configured for company '{company_id}'")
            if execution_id:
                job_history.mark_skipped(execution_id, "No Lucid URL configured")
            return {'success': False, 'skipped': True, 'reason': 'No Lucid URL configured'}

        logger.info(f"[{job_id}] Scraping Lucid Forum for {company_id}")

        # Import scraping functions
        from controllers.scraping import scrape_lucid_forum, export_lucid_posts_to_files
        from models.lucid_post import LucidPost
        from ai.haval_pipeline import start_haval_pipeline

        # Get parameters
        max_threads = parameters.get('max_threads', 10)
        max_posts = parameters.get('max_posts', 50)
        
        # Ensure values are integers
        try:
            max_threads = int(max_threads)
            max_posts = int(max_posts)
        except (ValueError, TypeError):
            logger.warning(f"[{job_id}] Invalid parameter values, using defaults")
            max_threads = 10
            max_posts = 50

        # Scrape Lucid forum
        posts = scrape_lucid_forum(
            base_url=lucid_url,
            max_threads=max_threads,
            max_posts=max_posts,
            delay=1.0
        )

        if not posts:
            logger.info(f"[{job_id}] No posts found")
            if execution_id:
                job_history.mark_skipped(execution_id, "No posts found")
            return {'success': False, 'skipped': True, 'reason': 'No posts found'}

        total_posts_scraped = len(posts)
        logger.info(f"[{job_id}] Scraped {total_posts_scraped} posts")

        # Save to database
        total_posts_saved = 0
        total_posts_skipped = 0
        
        try:
            # Group posts by thread
            threads_by_url = {}
            for post in posts:
                thread_url = post.get('thread_url', lucid_url)
                if thread_url not in threads_by_url:
                    threads_by_url[thread_url] = []
                threads_by_url[thread_url].append(post)
            
            # Save each thread's posts
            for thread_url, thread_posts in threads_by_url.items():
                saved, skipped = LucidPost.save_lucid_posts_to_db(
                    thread_link=thread_url,
                    posts=thread_posts,
                    user_id=1,  # System user
                    company_id=company_id
                )
                total_posts_saved += saved
                total_posts_skipped += skipped
                logger.info(f"[{job_id}] Saved {saved} posts, skipped {skipped} duplicates from {thread_url}")
        except Exception as e:
            logger.error(f"[{job_id}] Error saving posts to database: {e}", exc_info=True)

        # Export to files
        try:
            json_path, csv_path = export_lucid_posts_to_files(lucid_url, posts, company_id=company_id)
            logger.info(f"[{job_id}] Exported to {json_path}")

            # Run AI pipeline (if posts were saved)
            if total_posts_saved > 0:
                logger.info(f"[{job_id}] Starting AI pipeline")
                start_haval_pipeline(
                    json_path=json_path,
                    topic_url=f"lucid_forum_{lucid_url.split('/')[-1]}",
                    sources="Lucid Forum",
                    company_id=company_id
                )
        except Exception as e:
            logger.error(f"[{job_id}] Error in export/pipeline: {e}", exc_info=True)

        # Mark as successful
        message = f"Scraped {total_posts_scraped} posts: {total_posts_saved} saved, {total_posts_skipped} duplicates"
        logger.info(f"[{job_id}] Completed: {message}")

        if execution_id:
            job_history.mark_success(execution_id, message, records=total_posts_saved)

        return {
            'success': True,
            'posts_scraped': total_posts_scraped,
            'posts_saved': total_posts_saved,
            'posts_skipped': total_posts_skipped
        }

    except Exception as e:
        logger.error(f"[{job_id}] Job failed: {e}", exc_info=True)
        if execution_id:
            job_history.mark_failed(execution_id, str(e))
        return {'success': False, 'error': str(e)}


def scrape_reddit_lucid_job(job_config, job_id):
    """
    Scheduled Reddit Lucid scraping job.

    Scrapes Lucid Motors discussions from r/lucidmotors and r/LUCID.

    Args:
        job_config (dict): Job configuration from YAML
        job_id (str): Job identifier

    Returns:
        dict: Execution result
    """
    company_id = job_config.get('company_id', 'lucid')
    parameters = job_config.get('parameters', {})

    # Start tracking
    execution_id = job_history.start_execution(job_id, company_id)

    try:
        # Check pipeline status
        from ai.haval_pipeline import get_pipeline_status
        status = get_pipeline_status()

        if status.get('status') in ('processing', 'enriching', 'indexing'):
            logger.warning(f"[{job_id}] Pipeline busy ({status.get('status')}), skipping scheduled execution")
            if execution_id:
                job_history.mark_skipped(execution_id, f"Pipeline busy: {status.get('status')}")
            return {'success': False, 'skipped': True, 'reason': 'Pipeline busy'}

        # Get company configuration
        from config.companies import get_company_config
        company_config = get_company_config(company_id)

        if not company_config:
            raise ValueError(f"Company configuration not found for '{company_id}'")

        # Get Reddit URLs for Lucid
        reddit_urls = company_config.get_all_reddit_urls()

        if not reddit_urls:
            logger.warning(f"[{job_id}] No Reddit URLs configured for company '{company_id}'")
            if execution_id:
                job_history.mark_skipped(execution_id, "No Reddit URLs configured")
            return {'success': False, 'skipped': True, 'reason': 'No Reddit URLs configured'}

        logger.info(f"[{job_id}] Scraping Reddit Lucid for {company_id}: {reddit_urls}")

        # Import scraping functions
        from controllers.scrape_reddit_lucid import scrape_reddit_lucid_loop, export_reddit_lucid_to_json
        from ai.haval_pipeline import start_haval_pipeline

        # Get parameters
        max_posts = parameters.get('max_posts', 100)
        delay = parameters.get('delay', 5)
        
        # Ensure values are integers
        try:
            max_posts = int(max_posts)
            delay = int(delay)
        except (ValueError, TypeError):
            logger.warning(f"[{job_id}] Invalid parameter values, using defaults")
            max_posts = 100
            delay = 5

        # Scrape Reddit Lucid subreddits
        scrape_results = scrape_reddit_lucid_loop(
            subreddits=reddit_urls,
            max_posts_per_subreddit=max_posts,
            delay_between_subreddits=delay
        )

        total_posts_scraped = scrape_results.get('total_posts', 0)
        total_posts_saved = scrape_results.get('total_saved', 0)
        total_posts_skipped = scrape_results.get('total_skipped', 0)

        if total_posts_scraped == 0:
            logger.info(f"[{job_id}] No posts found")
            if execution_id:
                job_history.mark_skipped(execution_id, "No posts found")
            return {'success': False, 'skipped': True, 'reason': 'No posts found'}

        logger.info(f"[{job_id}] Scraped {total_posts_scraped} posts: {total_posts_saved} saved, {total_posts_skipped} duplicates")

        # Export to JSON
        try:
            json_path = export_reddit_lucid_to_json(company_id=company_id)
            
            if json_path:
                logger.info(f"[{job_id}] Exported to {json_path}")

                # Run AI pipeline (if posts were saved)
                if total_posts_saved > 0:
                    logger.info(f"[{job_id}] Starting AI pipeline")
                    start_haval_pipeline(
                        json_path=json_path,
                        topic_url="reddit_lucid_motors",
                        sources="Reddit",
                        company_id=company_id
                    )
        except Exception as e:
            logger.error(f"[{job_id}] Error in export/pipeline: {e}", exc_info=True)

        # Mark as successful
        message = f"Scraped {total_posts_scraped} posts: {total_posts_saved} saved, {total_posts_skipped} duplicates"
        logger.info(f"[{job_id}] Completed: {message}")

        if execution_id:
            job_history.mark_success(execution_id, message, records=total_posts_saved)

        return {
            'success': True,
            'posts_scraped': total_posts_scraped,
            'posts_saved': total_posts_saved,
            'posts_skipped': total_posts_skipped,
            'subreddits_processed': scrape_results.get('subreddits_processed', [])
        }

    except Exception as e:
        logger.error(f"[{job_id}] Job failed: {e}", exc_info=True)
        if execution_id:
            job_history.mark_failed(execution_id, str(e))
        return {'success': False, 'error': str(e)}


# Job function registry
# Maps job type to job function
JOB_FUNCTIONS = {
    'pakwheels': scrape_pakwheels_job,
    'reddit': scrape_reddit_job,
    'wati': import_wati_job,
    'lucid': scrape_lucid_job,
    'reddit_lucid': scrape_reddit_lucid_job,
}
