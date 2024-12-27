import os
from openalex_analyzer import OpenAlexAnalyzer
import plotly.io as pio
import networkx as nx
from datetime import datetime
import numpy as np

def get_institution_name(analyzer, institution_id: str) -> str:
    """Get institution name from OpenAlex API"""
    try:
        response = analyzer._make_request(f'institutions/{institution_id}')
        return response.get('display_name', '').replace(' ', '_')
    except:
        return ''

def main():
    # Initialize analyzer
    analyzer = OpenAlexAnalyzer(email="ahanmr98@gmail.com")
    
    # Example institution ID (University of Washington: I127803138)
    institution_id = "I97018004"
    
    # Get institution name
    institution_name = get_institution_name(analyzer, institution_id)
    
    # Create results directory with timestamp and institution info
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dir_name = f'results_{institution_id}'
    if institution_name:
        dir_name += f'_{institution_name}'
    dir_name += f'_{timestamp}'
    
    os.makedirs(dir_name, exist_ok=True)
    
    # Get collaboration data
    df = analyzer.get_institution_collaborations(
        institution_id=institution_id,
        start_year=2020,
        end_year=2023
    )
    
    # Save raw data
    df.to_csv(f'{dir_name}/collaboration_data.csv', index=False)
    
    # Create and save all visualizations
    visualizations = {
        'collaborations_over_time': analyzer.visualize_collaborations_over_time(df),
        'collaboration_map': analyzer.create_collaboration_map(df),
        'collaboration_trends': analyzer.create_collaboration_trends(df, top_n=10),
        'institution_network_top20': analyzer.create_institution_network_visualization(df, top_n=20),
        'institution_network_top50': analyzer.create_institution_network_visualization(df, top_n=50),
        'collaboration_summary': analyzer.create_collaboration_summary(df)
    }
    
    # Save all visualizations
    for name, fig in visualizations.items():
        pio.write_html(fig, f'{dir_name}/{name}.html')
    
    # Create and save network graph
    network = analyzer.create_collaboration_network(df)
    nx.write_gexf(network, f'{dir_name}/collaboration_network.gexf')
    
    print(f"Analysis complete! Results saved in '{dir_name}' folder")

if __name__ == "__main__":
    main() 