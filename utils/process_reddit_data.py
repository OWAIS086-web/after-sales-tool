"""
Script to process existing Reddit JSON data through the pipeline.
This will create conversation blocks and index them into ChromaDB.
"""
import time
from ai.haval_pipeline import start_haval_pipeline, get_pipeline_status

def main():
    print("=" * 60)
    print("Processing Reddit Data for Haval")
    print("=" * 60)

    # Path to your existing Reddit JSON file
    json_path = "data/reddit_search_haval car.json"

    # Start the pipeline
    print(f"\n📊 Starting pipeline for: {json_path}")
    print("⏳ This will:")
    print("   1. Convert Reddit posts to conversation blocks")
    print("   2. Classify and enrich blocks")
    print("   3. Index into ChromaDB vector store")
    print("   4. Create reddit_blocks_haval.pkl")

    start_haval_pipeline(
        json_path=json_path,
        topic_url="",  # Not needed for Reddit
        sources="Reddit",  # Important: This tells it to use Reddit processing
        company_id="haval"
    )

    print("\n✅ Pipeline started in background!")
    print("📈 Monitoring progress...\n")

    # Monitor progress
    while True:
        status = get_pipeline_status()
        current_status = status.get("status", "unknown")
        current_step = status.get("current_step", "unknown")
        total_blocks = status.get("total_blocks", 0)
        error = status.get("error")

        if current_status == "completed":
            print(f"\n✅ Pipeline completed successfully!")
            print(f"   Total blocks created: {total_blocks}")
            print(f"   ChromaDB indexed: haval_reddit_blocks")
            print(f"   Pickle file: data/reddit_blocks_haval.pkl")
            break
        elif current_status == "failed":
            print(f"\n❌ Pipeline failed!")
            print(f"   Error: {error}")
            break
        else:
            print(f"⏳ Status: {current_status.upper()} | Step: {current_step} | Blocks: {total_blocks}", end="\r")

        time.sleep(2)

if __name__ == "__main__":
    main()
