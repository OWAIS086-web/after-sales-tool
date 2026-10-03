"""
Comprehensive Test Suite for Query Type Fix
============================================

Tests 20 diverse queries covering:
- All tiers (0, 1, 2, 3)
- All query types (aggregate, hybrid, listing)
- Edge cases and failures
- Queries from meeting_notes.txt, successful_queries.txt, tested_queries_DMS.txt

Output: Saves detailed results to comprehensive_test_results.txt
"""

import sys
from datetime import datetime
from ai.dms_engine.dms_pipeline import DMSPipeline


class TestLogger:
    """Logger that writes to both console and file"""

    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, 'w', encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def close(self):
        self.log.close()


def test_query(pipeline, test_num, query_text, expected_type=None, expected_tier=None, description=""):
    """Test a single query with detailed logging"""
    print("\n" + "=" * 100)
    print(f"TEST #{test_num}: {description}")
    print("=" * 100)
    print(f"Query: {query_text}")
    if expected_type:
        print(f"Expected Query Type: {expected_type}")
    if expected_tier:
        print(f"Expected Tier: {expected_tier}")
    print("-" * 100)

    try:
        start_time = datetime.now()
        result = pipeline.query(query_text)
        end_time = datetime.now()

        # Extract metadata
        actual_tier = result.tier_used
        actual_type = result.metadata.get('query_type', 'N/A') if result.metadata else 'N/A'
        execution_time = result.execution_time

        # Validation
        tier_match = (actual_tier == expected_tier) if expected_tier else True
        type_match = (actual_type == expected_type) if expected_type else True

        # Status
        if result.success:
            status = "✅ SUCCESS"
            if expected_tier and not tier_match:
                status += f" (⚠️  Tier Mismatch: expected {expected_tier}, got {actual_tier})"
            if expected_type and not type_match:
                status += f" (⚠️  Type Mismatch: expected {expected_type}, got {actual_type})"
        else:
            status = "❌ FAILED"

        print(f"\n{status}")
        print(f"├─ Tier Used: {actual_tier}")
        print(f"├─ Query Type: {actual_type}")
        print(f"├─ Execution Time: {execution_time:.2f}s")
        print(f"├─ Result Count: {len(result.raw_results)} rows")

        if result.success:
            print(f"\n📊 ANSWER:")
            print("-" * 100)
            print(result.natural_answer)
            print("-" * 100)

            if result.raw_results and len(result.raw_results) <= 5:
                print(f"\n📋 RAW RESULTS (all {len(result.raw_results)} rows):")
                for i, row in enumerate(result.raw_results, 1):
                    print(f"  Row {i}: {row}")
            elif result.raw_results:
                print(f"\n📋 RAW RESULTS (first 3 of {len(result.raw_results)} rows):")
                for i, row in enumerate(result.raw_results[:3], 1):
                    print(f"  Row {i}: {row}")
        else:
            print(f"\n❌ ERROR MESSAGE:")
            print(result.error_message)

        return {
            'test_num': test_num,
            'description': description,
            'query': query_text,
            'success': result.success,
            'tier': actual_tier,
            'query_type': actual_type,
            'expected_tier': expected_tier,
            'expected_type': expected_type,
            'tier_match': tier_match,
            'type_match': type_match,
            'execution_time': execution_time,
            'row_count': len(result.raw_results)
        }

    except Exception as e:
        print(f"\n💥 EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return {
            'test_num': test_num,
            'description': description,
            'query': query_text,
            'success': False,
            'tier': None,
            'query_type': None,
            'expected_tier': expected_tier,
            'expected_type': expected_type,
            'tier_match': False,
            'type_match': False,
            'execution_time': 0,
            'row_count': 0
        }


def main():
    # Setup logging
    log_filename = f"comprehensive_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    logger = TestLogger(log_filename)
    sys.stdout = logger

    print("=" * 100)
    print("COMPREHENSIVE TEST SUITE - Query Type Fix Validation")
    print("=" * 100)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output File: {log_filename}")
    print("=" * 100)

    # Initialize pipeline
    print("\n[SETUP] Initializing DMS Pipeline...")
    pipeline = DMSPipeline(
        db_path="data/SazgarDMSDW.sqlite",
        dealer_id=None,  # Test without RLS
        verbose=False  # Less verbose for cleaner output
    )
    print("✓ Pipeline initialized\n")

    # Test Suite: 20 diverse queries
    test_cases = [
        # ========================================
        # CATEGORY 1: AGGREGATE QUERIES (Tier 0/3)
        # ========================================
        {
            'query': "How many repair orders?",
            'expected_type': 'aggregate',
            'expected_tier': 0,  # Likely Tier 0 hardcoded
            'description': "Simple count - Tier 0 hardcoded"
        },
        {
            'query': "what are the total unique vin numbers in the data base??",
            'expected_type': 'aggregate',
            'expected_tier': 3,  # Full RAG
            'description': "Distinct count - database-wide (FIXED BUG)"
        },
        {
            'query': "what are the total unique vin numbers in the table RO Master",
            'expected_type': 'aggregate',
            'expected_tier': 3,  # Should be Tier 3, but may hit Tier 2
            'description': "Distinct count - specific table (FAILING IN TIER 2)"
        },
        {
            'query': "Total SFS inspections across all dealerships",
            'expected_type': 'aggregate',
            'expected_tier': None,  # Could be Tier 0 or 3
            'description': "Count across all entities"
        },
        {
            'query': "What percentage of PDIs had objections?",
            'expected_type': 'aggregate',
            'expected_tier': 3,
            'description': "Percentage calculation"
        },
        {
            'query': "How many campaigns in 2025?",
            'expected_type': 'aggregate',
            'expected_tier': None,
            'description': "Campaign count with year filter"
        },

        # ========================================
        # CATEGORY 2: HYBRID QUERIES (Grouped Aggregates)
        # ========================================
        {
            'query': "Which dealership has the most repair orders?",
            'expected_type': 'hybrid',
            'expected_tier': 0,  # Likely Tier 0
            'description': "Ranking query - dealership"
        },
        {
            'query': "Which VINs have the highest complaint count?",
            'expected_type': 'hybrid',
            'expected_tier': 2,  # Likely Tier 2 view
            'description': "Ranking query - VINs"
        },
        {
            'query': "Show monthly repair order counts for 2024",
            'expected_type': 'hybrid',
            'expected_tier': 3,
            'description': "Time-based grouping"
        },
        {
            'query': "Which dealership performed most SFS?",
            'expected_type': 'hybrid',
            'expected_tier': None,
            'description': "SFS ranking by dealership"
        },
        {
            'query': "Show average CSI score by dealership",
            'expected_type': 'hybrid',
            'expected_tier': 3,
            'description': "Average grouped by dealer"
        },
        {
            'query': "Compare sales vs PDI completion rate by dealership",
            'expected_type': 'hybrid',
            'expected_tier': 3,
            'description': "Comparison query"
        },

        # ========================================
        # CATEGORY 3: LISTING QUERIES (Entity Rows)
        # ========================================
        {
            'query': "Show me repair history for VIN NF9FF6A58N2000096",
            'expected_type': 'listing',
            'expected_tier': 1,  # Likely Tier 1 template
            'description': "VIN history lookup"
        },
        {
            'query': "How many PDI reports?",
            'expected_type': 'aggregate',
            'expected_tier': 0,
            'description': "PDI count - simple aggregate"
        },
        {
            'query': "How many vehicles were sold in 2023?",
            'expected_type': 'aggregate',
            'expected_tier': 3,
            'description': "Vehicle sales count by year"
        },
        {
            'query': "List all campaigns",
            'expected_type': 'listing',
            'expected_tier': 3,
            'description': "Campaign listing query"
        },

        # ========================================
        # CATEGORY 4: COMPLEX QUERIES
        # ========================================
        {
            'query': "Which issues have been repeatedly reported for VIN NF9FF6A58N2000096?",
            'expected_type': None,  # Could be hybrid or listing
            'expected_tier': 3,
            'description': "Pattern detection query"
        },
        {
            'query': "Which vehicle models are most popular?",
            'expected_type': 'hybrid',
            'expected_tier': 3,
            'description': "Vehicle model popularity ranking"
        },

        # ========================================
        # CATEGORY 5: EDGE CASES
        # ========================================
        {
            'query': "How many campaigns in October 2030?",
            'expected_type': 'aggregate',
            'expected_tier': None,
            'description': "Zero results - future date"
        },
        {
            'query': "How many vehicles completed first free service?",
            'expected_type': 'aggregate',
            'expected_tier': None,
            'description': "FFS completion count"
        },
    ]

    # Run tests
    results = []
    for i, test_case in enumerate(test_cases, 1):
        result = test_query(
            pipeline=pipeline,
            test_num=i,
            query_text=test_case['query'],
            expected_type=test_case.get('expected_type'),
            expected_tier=test_case.get('expected_tier'),
            description=test_case['description']
        )
        results.append(result)

    # Summary Report
    print("\n" + "=" * 100)
    print("TEST SUMMARY REPORT")
    print("=" * 100)

    # Overall stats
    total_tests = len(results)
    successful = sum(1 for r in results if r['success'])
    failed = total_tests - successful

    # Tier distribution
    tier_counts = {}
    for r in results:
        tier = r['tier']
        if tier is not None:
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

    # Query type distribution
    type_counts = {}
    for r in results:
        qtype = r['query_type']
        if qtype and qtype != 'N/A':
            type_counts[qtype] = type_counts.get(qtype, 0) + 1

    # Validation stats
    tier_matches = sum(1 for r in results if r['tier_match'])
    type_matches = sum(1 for r in results if r['type_match'])

    print(f"\n📊 OVERALL STATISTICS:")
    print(f"├─ Total Tests: {total_tests}")
    print(f"├─ Successful: {successful} ({successful/total_tests*100:.0f}%)")
    print(f"├─ Failed: {failed} ({failed/total_tests*100:.0f}%)")

    print(f"\n🎯 TIER DISTRIBUTION:")
    for tier in sorted(tier_counts.keys()):
        count = tier_counts[tier]
        print(f"├─ Tier {tier}: {count} queries ({count/successful*100:.0f}%)")

    print(f"\n🔍 QUERY TYPE DISTRIBUTION:")
    for qtype in sorted(type_counts.keys()):
        count = type_counts[qtype]
        print(f"├─ {qtype}: {count} queries ({count/successful*100:.0f}%)")

    print(f"\n✅ VALIDATION ACCURACY:")
    expected_tier_tests = sum(1 for r in results if r['expected_tier'] is not None)
    expected_type_tests = sum(1 for r in results if r['expected_type'] is not None)
    if expected_tier_tests > 0:
        print(f"├─ Tier Prediction: {tier_matches}/{expected_tier_tests} correct ({tier_matches/expected_tier_tests*100:.0f}%)")
    if expected_type_tests > 0:
        print(f"├─ Query Type Detection: {type_matches}/{expected_type_tests} correct ({type_matches/expected_type_tests*100:.0f}%)")

    # Detailed breakdown
    print(f"\n📋 DETAILED TEST RESULTS:")
    print("-" * 100)
    print(f"{'#':<4} {'Status':<10} {'Tier':<6} {'Type':<12} {'Time':<8} {'Rows':<8} {'Description':<40}")
    print("-" * 100)

    for r in results:
        status_icon = "✅" if r['success'] else "❌"
        tier_str = f"T{r['tier']}" if r['tier'] is not None else "N/A"
        type_str = (r['query_type'] if r['query_type'] else "N/A")[:10]
        time_str = f"{r['execution_time']:.2f}s"
        rows_str = str(r['row_count'])
        desc_str = r['description'][:38]

        print(f"{r['test_num']:<4} {status_icon:<10} {tier_str:<6} {type_str:<12} {time_str:<8} {rows_str:<8} {desc_str:<40}")

    print("-" * 100)

    # Failed tests detail
    failed_tests = [r for r in results if not r['success']]
    if failed_tests:
        print(f"\n❌ FAILED TESTS ({len(failed_tests)}):")
        for r in failed_tests:
            print(f"\n  Test #{r['test_num']}: {r['description']}")
            print(f"  Query: {r['query']}")

    # Tier/Type mismatches
    tier_mismatches = [r for r in results if not r['tier_match'] and r['expected_tier'] is not None]
    if tier_mismatches:
        print(f"\n⚠️  TIER MISMATCHES ({len(tier_mismatches)}):")
        for r in tier_mismatches:
            print(f"\n  Test #{r['test_num']}: {r['description']}")
            print(f"  Expected: Tier {r['expected_tier']}, Got: Tier {r['tier']}")

    type_mismatches = [r for r in results if not r['type_match'] and r['expected_type'] is not None]
    if type_mismatches:
        print(f"\n⚠️  QUERY TYPE MISMATCHES ({len(type_mismatches)}):")
        for r in type_mismatches:
            print(f"\n  Test #{r['test_num']}: {r['description']}")
            print(f"  Expected: {r['expected_type']}, Got: {r['query_type']}")

    # Key Findings
    print(f"\n🔑 KEY FINDINGS:")
    print("=" * 100)

    # Check if the main bug is fixed
    bug_test = next((r for r in results if "FIXED BUG" in r['description']), None)
    if bug_test and bug_test['success'] and bug_test['query_type'] == 'aggregate':
        print("✅ PRIMARY BUG FIXED: Distinct count queries generate correct COUNT(DISTINCT) SQL")
    else:
        print("❌ PRIMARY BUG STILL PRESENT: Distinct count queries not working")

    # Check tier 2 issue
    tier2_issue = next((r for r in results if "FAILING IN TIER 2" in r['description']), None)
    if tier2_issue and tier2_issue['tier'] == 2:
        print("❌ TIER 2 ROUTING ISSUE: Query matched wrong view in Tier 2")
    elif tier2_issue and tier2_issue['tier'] == 3:
        print("✅ TIER 2 ROUTING FIXED: Query correctly routed to Tier 3")

    # Check query type accuracy
    if type_matches / max(expected_type_tests, 1) >= 0.9:
        print("✅ QUERY TYPE DETECTION: High accuracy (≥90%)")
    elif type_matches / max(expected_type_tests, 1) >= 0.7:
        print("⚠️  QUERY TYPE DETECTION: Moderate accuracy (70-90%)")
    else:
        print("❌ QUERY TYPE DETECTION: Low accuracy (<70%)")

    # Performance insights
    avg_time = sum(r['execution_time'] for r in results if r['success']) / max(successful, 1)
    tier0_tests = [r for r in results if r['tier'] == 0 and r['success']]
    tier3_tests = [r for r in results if r['tier'] == 3 and r['success']]

    if tier0_tests:
        avg_tier0_time = sum(r['execution_time'] for r in tier0_tests) / len(tier0_tests)
        print(f"⚡ TIER 0 PERFORMANCE: Avg {avg_tier0_time:.2f}s (fast path working)")

    if tier3_tests:
        avg_tier3_time = sum(r['execution_time'] for r in tier3_tests) / len(tier3_tests)
        print(f"🐌 TIER 3 PERFORMANCE: Avg {avg_tier3_time:.2f}s (full RAG pipeline)")

    print("=" * 100)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Results saved to: {log_filename}")
    print("=" * 100)

    # Cleanup
    logger.close()
    sys.stdout = logger.terminal

    # Exit code
    if successful == total_tests:
        print(f"\n🎉 ALL TESTS PASSED! ({successful}/{total_tests})")
        return 0
    else:
        print(f"\n⚠️  SOME TESTS FAILED ({failed}/{total_tests})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
