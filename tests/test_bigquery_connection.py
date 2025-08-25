#!/usr/bin/env python3
"""
BigQuery Connection Test

Quick test to verify BigQuery authentication and access to TheLook dataset
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from design.bigquery_utils import BigQueryTrafficAnalyzer

def test_bigquery_connection():
    """Test BigQuery connection and data access"""
    print("🔍 Testing BigQuery connection...")
    
    # Test 1: Initialize analyzer without mock data
    try:
        analyzer = BigQueryTrafficAnalyzer(use_mock_data=False)
        print("✅ BigQuery client initialized successfully")
    except Exception as e:
        print(f"❌ BigQuery client initialization failed: {e}")
        return False
    
    # Test 2: Validate connection
    try:
        connection_valid = analyzer.validate_connection()
        if connection_valid:
            print("✅ BigQuery connection validated")
        else:
            print("❌ BigQuery connection validation failed")
            return False
    except Exception as e:
        print(f"❌ Connection validation error: {e}")
        return False
    
    # Test 3: Test simple query to TheLook dataset
    try:
        print("🔍 Testing access to TheLook dataset...")
        from google.cloud import bigquery
        
        client = bigquery.Client()
        query = """
        SELECT COUNT(*) as user_count
        FROM `bigquery-public-data.thelook_ecommerce.users`
        LIMIT 1
        """
        
        result = client.query(query).result()
        for row in result:
            print(f"✅ TheLook dataset accessible - found {row.user_count:,} users")
            return True
            
    except Exception as e:
        print(f"❌ TheLook dataset access failed: {e}")
        return False
    
    return True

def main():
    """Main test runner"""
    print("🧪 BigQuery Connection Test")
    print("=" * 50)
    
    success = test_bigquery_connection()
    
    if success:
        print("\n🎉 All tests passed! BigQuery is ready to use.")
        print("\nYou can now run power analysis with:")
        print("python run_power_analysis.py free_shipping_threshold_test")
        sys.exit(0)
    else:
        print("\n❌ BigQuery setup needs attention.")
        print("\n🛠️ Next steps:")
        print("1. Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install")
        print("2. Run: gcloud auth login")
        print("3. Run: gcloud auth application-default login")
        print("4. Ensure you have access to BigQuery API")
        sys.exit(1)

if __name__ == "__main__":
    main()