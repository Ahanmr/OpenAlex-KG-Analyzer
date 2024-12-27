import os
import pandas as pd
import requests
from datetime import datetime
import logging

class InstitutionFetcher:
    def __init__(self, email: str):
        self.base_url = "https://api.openalex.org"
        self.email = email
        self.headers = {'User-Agent': f'mailto:{email}'}
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make a request to the OpenAlex API"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            raise

    def fetch_institutions(self, per_page: int = 200, max_pages: int = None) -> pd.DataFrame:
        """
        Fetch institutions from OpenAlex API
        
        Args:
            per_page (int): Number of results per page
            max_pages (int): Maximum number of pages to fetch (None for all)
        """
        params = {
            'per-page': per_page,
            'page': 1,
            # Sort by works count to get most relevant institutions first
            'sort': 'works_count:desc'
        }
        
        institutions = []
        total_processed = 0
        
        while True:
            self.logger.info(f"Fetching page {params['page']}. Total processed: {total_processed}")
            
            response = self._make_request('institutions', params)
            
            if not response.get('results'):
                break
                
            for inst in response['results']:
                institutions.append({
                    'openalex_id': inst['id'],
                    'display_name': inst.get('display_name', ''),
                    'country_code': inst.get('country_code', ''),
                    'type': inst.get('type', ''),
                    'works_count': inst.get('works_count', 0),
                    'cited_by_count': inst.get('cited_by_count', 0),
                    'ror_id': inst.get('ror', ''),
                    'homepage_url': inst.get('homepage_url', ''),
                    'image_url': inst.get('image_url', '')
                })
            
            total_processed += len(response['results'])
            
            # Check if we've reached max_pages
            if max_pages and params['page'] >= max_pages:
                self.logger.info(f"Reached maximum pages limit: {max_pages}")
                break
                
            # Check if there are more pages
            if total_processed >= response['meta']['count']:
                break
                
            params['page'] += 1
        
        self.logger.info(f"Total institutions fetched: {len(institutions)}")
        return pd.DataFrame(institutions)

def main():
    # Create output directory with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = f'institution_data_{timestamp}'
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize fetcher
    fetcher = InstitutionFetcher(email="ahanmr98@gmail.com")
    
    # Fetch institutions (adjust max_pages as needed)
    df = fetcher.fetch_institutions(max_pages=50)  # Fetches first 50 pages
    
    # Save full dataset
    df.to_csv(f'{output_dir}/institutions_full.csv', index=False)
    
    # Save a simplified version with just ID and name
    df_simple = df[['openalex_id', 'display_name', 'country_code', 'type', 'works_count']]
    df_simple.to_csv(f'{output_dir}/institutions_simple.csv', index=False)
    
    # Create a markdown file with top institutions
    top_institutions = df.nlargest(100, 'works_count')
    with open(f'{output_dir}/top_institutions.md', 'w', encoding='utf-8') as f:
        f.write("# Top 100 Institutions by Works Count\n\n")
        f.write("| OpenAlex ID | Institution Name | Country | Works Count |\n")
        f.write("|-------------|------------------|---------|-------------|\n")
        for _, row in top_institutions.iterrows():
            f.write(f"| {row['openalex_id']} | {row['display_name']} | {row['country_code']} | {row['works_count']:,} |\n")
    
    # Create a summary file
    with open(f'{output_dir}/summary.txt', 'w', encoding='utf-8') as f:
        f.write("Institution Data Summary\n")
        f.write("======================\n\n")
        f.write(f"Total institutions: {len(df):,}\n")
        f.write(f"Countries represented: {df['country_code'].nunique():,}\n")
        
        # Handle None values in institution types
        institution_types = [str(t) for t in df['type'].unique() if pd.notna(t)]
        f.write(f"Institution types: {', '.join(institution_types)}\n\n")
        
        f.write("Top 10 countries by number of institutions:\n")
        country_counts = df['country_code'].value_counts().head(10)
        for country, count in country_counts.items():
            f.write(f"- {country}: {count:,}\n")
    
    print(f"Data saved in '{output_dir}' directory:")
    print(f"- Full dataset: institutions_full.csv")
    print(f"- Simplified dataset: institutions_simple.csv")
    print(f"- Top institutions: top_institutions.md")
    print(f"- Summary: summary.txt")

if __name__ == "__main__":
    main() 