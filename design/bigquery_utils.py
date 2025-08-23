# design/bigquery_utils.py
"""
BigQuery Utilities for Traffic Analysis

This module handles all BigQuery interaction complexity, including:
- Authentication management
- Query building based on TheLook schema
- Error handling and retries
- Mock data for development/testing

Separated from power_analysis.py to improve testability and maintainability.
"""

import pandas as pd
from google.cloud import bigquery
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BigQueryTrafficAnalyzer:
    """
    Handles BigQuery traffic analysis with proper error handling and authentication
    """
    
    def __init__(self, project_id: Optional[str] = None, use_mock_data: bool = False):
        """
        Initialize BigQuery client with flexible authentication
        
        Args:
            project_id: Optional project ID (uses default if None)
            use_mock_data: If True, returns mock data instead of querying BigQuery
        """
        self.use_mock_data = use_mock_data
        self.project_id = project_id
        
        if not use_mock_data:
            try:
                if project_id:
                    self.client = bigquery.Client(project=project_id)
                else:
                    # Use default project from environment
                    self.client = bigquery.Client()
                
                logger.info(f"BigQuery client initialized for project: {self.client.project}")
                
            except Exception as e:
                logger.warning(f"BigQuery client initialization failed: {e}")
                logger.warning("Falling back to mock data for development")
                self.use_mock_data = True
        
        if self.use_mock_data:
            logger.info("Using mock data for traffic analysis")
    
    def analyze_traffic_patterns(self, eligibility_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze historical traffic patterns based on eligibility criteria
        
        Returns realistic traffic estimates whether using real BigQuery or mock data
        """
        if self.use_mock_data:
            return self._get_mock_traffic_data(eligibility_criteria)
        
        return self._analyze_bigquery_traffic(eligibility_criteria)
    
    def _analyze_bigquery_traffic(self, eligibility_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze traffic using real BigQuery data from TheLook
        """
        # Build query based on actual TheLook schema
        query = self._build_thelook_traffic_query(eligibility_criteria)
        
        try:
            logger.info("Executing BigQuery traffic analysis...")
            
            # Execute query with timeout
            job_config = bigquery.QueryJobConfig()
            job_config.query_parameters = []
            
            query_job = self.client.query(query, job_config=job_config)
            
            # Wait for results with timeout
            result_df = query_job.to_dataframe()
            
            if len(result_df) == 0:
                raise ValueError("No data returned from BigQuery. Check eligibility criteria.")
            
            # Process results
            return self._process_bigquery_results(result_df)
            
        except Exception as e:
            logger.error(f"BigQuery traffic analysis failed: {e}")
            logger.info("Falling back to mock data")
            return self._get_mock_traffic_data(eligibility_criteria)
    
    def _build_thelook_traffic_query(self, eligibility_criteria: Dict[str, Any]) -> str:
        """
        Build BigQuery query based on actual TheLook schema
        
        Fixed to work with real TheLook data structure
        """
        # Build WHERE conditions based on eligibility
        where_conditions = []
        
        # Include conditions
        include_criteria = eligibility_criteria.get('include', {})
        
        # Countries - TheLook has 'country' field
        if 'countries' in include_criteria:
            countries = include_criteria['countries']
            country_list = "', '".join(countries)
            where_conditions.append(f"users.country IN ('{country_list}')")
        
        # Customer types - we'll infer from order history
        if 'customer_types' in include_criteria:
            customer_types = include_criteria['customer_types']
            if 'new' in customer_types and 'returning' not in customer_types:
                # Only new customers
                where_conditions.append("""
                    users.id NOT IN (
                        SELECT DISTINCT user_id 
                        FROM `bigquery-public-data.thelook_ecommerce.orders` o2 
                        WHERE o2.created_at < users.created_at
                    )
                """)
            elif 'returning' in customer_types and 'new' not in customer_types:
                # Only returning customers
                where_conditions.append("""
                    users.id IN (
                        SELECT DISTINCT user_id 
                        FROM `bigquery-public-data.thelook_ecommerce.orders` o2 
                        WHERE o2.created_at < users.created_at
                    )
                """)
            # If both 'new' and 'returning', no additional filter needed
        
        # Exclude conditions
        exclude_criteria = eligibility_criteria.get('exclude', {})
        
        if exclude_criteria.get('vip_customers'):
            # Exclude users with lifetime value > $1000
            where_conditions.append("""
                users.id NOT IN (
                    SELECT user_id
                    FROM `bigquery-public-data.thelook_ecommerce.orders`
                    GROUP BY user_id
                    HAVING SUM(sale_price) > 1000
                )
            """)
        
        if exclude_criteria.get('employee_accounts'):
            where_conditions.append("users.email NOT LIKE '%@thelook.com'")
            where_conditions.append("users.email NOT LIKE '%employee%'")
        
        if exclude_criteria.get('test_accounts'):
            where_conditions.append("users.email NOT LIKE '%test%'")
            where_conditions.append("users.first_name NOT LIKE '%Test%'")
        
        # Combine all conditions
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Build the complete query
        query = f"""
        WITH daily_user_stats AS (
            SELECT 
                DATE(users.created_at) as date,
                COUNT(DISTINCT users.id) as daily_users,
                
                -- Calculate same-day conversion (proxy for session conversion)
                COUNT(DISTINCT CASE 
                    WHEN orders.user_id IS NOT NULL 
                    AND DATE(orders.created_at) = DATE(users.created_at)
                    THEN users.id 
                END) as same_day_converters,
                
                -- Calculate average order value for context
                AVG(CASE 
                    WHEN orders.order_id IS NOT NULL 
                    AND DATE(orders.created_at) = DATE(users.created_at)
                    THEN orders.sale_price 
                END) as avg_same_day_order_value,
                
                -- Day of week for pattern analysis
                EXTRACT(DAYOFWEEK FROM users.created_at) as day_of_week
                
            FROM `bigquery-public-data.thelook_ecommerce.users` users
            LEFT JOIN `bigquery-public-data.thelook_ecommerce.orders` orders
                ON users.id = orders.user_id 
                AND DATE(orders.created_at) = DATE(users.created_at)
            
            WHERE {where_clause}
                AND DATE(users.created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
                AND DATE(users.created_at) < CURRENT_DATE()
                AND users.email IS NOT NULL
                AND users.country IS NOT NULL
            
            GROUP BY DATE(users.created_at), EXTRACT(DAYOFWEEK FROM users.created_at)
        ),
        
        summary_stats AS (
            SELECT 
                AVG(daily_users) as avg_daily_users,
                STDDEV(daily_users) as stddev_daily_users,
                MIN(daily_users) as min_daily_users,
                MAX(daily_users) as max_daily_users,
                AVG(SAFE_DIVIDE(same_day_converters, daily_users)) as avg_conversion_rate,
                STDDEV(SAFE_DIVIDE(same_day_converters, daily_users)) as stddev_conversion_rate,
                AVG(avg_same_day_order_value) as overall_avg_order_value,
                COUNT(*) as days_analyzed,
                MIN(date) as analysis_start_date,
                MAX(date) as analysis_end_date
            FROM daily_user_stats
            WHERE daily_users > 0
        ),
        
        day_of_week_patterns AS (
            SELECT 
                day_of_week,
                AVG(daily_users) as avg_users_by_day,
                STDDEV(daily_users) as stddev_users_by_day,
                COUNT(*) as days_observed
            FROM daily_user_stats
            WHERE daily_users > 0
            GROUP BY day_of_week
        )
        
        SELECT 
            s.*,
            ARRAY_AGG(STRUCT(
                dow.day_of_week,
                dow.avg_users_by_day,
                COALESCE(dow.stddev_users_by_day, 0) as stddev_users_by_day,
                dow.days_observed
            ) ORDER BY dow.day_of_week) as day_of_week_patterns
        FROM summary_stats s
        CROSS JOIN day_of_week_patterns dow
        GROUP BY 
            s.avg_daily_users, s.stddev_daily_users, s.min_daily_users, s.max_daily_users,
            s.avg_conversion_rate, s.stddev_conversion_rate, s.overall_avg_order_value,
            s.days_analyzed, s.analysis_start_date, s.analysis_end_date
        """
        
        return query
    
    def _process_bigquery_results(self, result_df: pd.DataFrame) -> Dict[str, Any]:
        if len(result_df) == 0:
            raise ValueError("Empty results from BigQuery")
        
        row = result_df.iloc[0]
        day_patterns = {}
        
        if 'day_of_week_patterns' in row and row['day_of_week_patterns'] is not None:
            try:
                for pattern in row['day_of_week_patterns']:
                    if isinstance(pattern, dict):
                        day_patterns[pattern['day_of_week']] = {
                            'avg_users': float(pattern.get('avg_users_by_day', 0)),
                            'stddev_users': float(pattern.get('stddev_users_by_day', 0)),
                            'days_observed': int(pattern.get('days_observed', 0))
                        }
            except Exception as e:
                logger.warning(f"Could not parse day-of-week patterns: {e}")
        
        return {
            "avg_daily_eligible_users": int(row.get('avg_daily_users', 0)),
            "stddev_daily_eligible_users": int(row.get('stddev_daily_users', 0)),
            "min_daily_eligible_users": int(row.get('min_daily_users', 0)),
            "max_daily_eligible_users": int(row.get('max_daily_users', 0)),
            "historical_conversion_rate": float(row.get('avg_conversion_rate', 0) or 0),
            "conversion_rate_variability": float(row.get('stddev_conversion_rate', 0) or 0),
            "historical_aov": float(row.get('overall_avg_order_value', 0) or 0),
            "days_analyzed": int(row.get('days_analyzed', 0)),
            "analysis_period": {
                "start": row.get('analysis_start_date'),
                "end": row.get('analysis_end_date')
            },
            "day_of_week_patterns": day_patterns,
            "traffic_variability_coefficient": (
                float(row.get('stddev_daily_users', 0)) / float(row.get('avg_daily_users', 1))
                if row.get('avg_daily_users', 0) > 0 else 0
            ),
            "data_source": "bigquery_thelook",
            "query_success": True
        }
    
    def _get_mock_traffic_data(self, eligibility_criteria: Dict[str, Any]) -> Dict[str, Any]:
        base_daily_users = 1000
        
        include_criteria = eligibility_criteria.get('include', {})
        if 'countries' in include_criteria:
            num_countries = len(include_criteria['countries'])
            if num_countries <= 2:
                base_daily_users = int(base_daily_users * 0.3)
        
        exclude_criteria = eligibility_criteria.get('exclude', {})
        if exclude_criteria.get('vip_customers'):
            base_daily_users = int(base_daily_users * 0.95)
        
        traffic_cv = 0.15
        stddev_users = int(base_daily_users * traffic_cv)
        
        return {
            "avg_daily_eligible_users": base_daily_users,
            "stddev_daily_eligible_users": stddev_users,
            "min_daily_eligible_users": int(base_daily_users * 0.7),
            "max_daily_eligible_users": int(base_daily_users * 1.4),
            "historical_conversion_rate": 0.045,
            "conversion_rate_variability": 0.008,
            "historical_aov": 52.30,
            "days_analyzed": 90,
            "analysis_period": {
                "start": datetime.now() - timedelta(days=90),
                "end": datetime.now() - timedelta(days=1)
            },
            "day_of_week_patterns": {},
            "traffic_variability_coefficient": traffic_cv,
            "data_source": "mock_data",
            "query_success": False
        }
    
    def validate_connection(self) -> bool:
        if self.use_mock_data:
            return False
        
        try:
            test_query = "SELECT 1 as test_value"
            result = self.client.query(test_query).result()
            
            for row in result:
                if row.test_value == 1:
                    logger.info("BigQuery connection validated successfully")
                    return True
            return False
        except Exception as e:
            logger.error(f"BigQuery connection validation failed: {e}")
            return False