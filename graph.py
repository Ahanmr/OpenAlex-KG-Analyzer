import networkx as nx
import requests
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging
from collections import defaultdict
import plotly.graph_objects as go
import numpy as np
import os
from datetime import datetime
import csv
from tqdm import tqdm

class CoAuthorshipGraph:
    def __init__(self, email: str):
        """
        Initialize the co-authorship graph builder
        
        Args:
            email (str): Email for polite pool access to OpenAlex API
        """
        self.base_url = "https://api.openalex.org"
        self.headers = {'User-Agent': f'mailto:{email}'}
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Initialize graph
        self.graph = nx.Graph()
        
        # Create output directory with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = f'knowledge_graph_{timestamp}'
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Setup logging to file
        log_file = os.path.join(self.output_dir, 'graph_generation.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(file_handler)
        
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a request to the OpenAlex API"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            raise

    def build_coauthorship_network(self, 
                                 institution_id: str,
                                 start_year: int,
                                 end_year: int,
                                 max_papers: int = 1000) -> nx.Graph:
        """
        Build co-authorship network for an institution
        
        Args:
            institution_id (str): OpenAlex ID for the institution
            start_year (int): Start year for analysis
            end_year (int): End year for analysis
            max_papers (int): Maximum number of papers to analyze
            
        Returns:
            nx.Graph: NetworkX graph of co-authorship network
        """
        params = {
            'filter': f'institutions.id:{institution_id},'
                     f'publication_year:{start_year}-{end_year}',
            'per_page': 100,
            'cursor': '*'
        }
        
        # Track co-authorship frequencies
        coauthor_freq = defaultdict(int)
        # Track author publication counts
        author_pubs = defaultdict(int)
        # Store author metadata
        author_metadata = {}
        
        papers_processed = 0
        pbar = tqdm(total=max_papers, desc="Fetching papers")
        
        while papers_processed < max_papers:
            response = self._make_request('works', params)
            
            if not response.get('results'):
                break
                
            for work in response['results']:
                if papers_processed >= max_papers:
                    break
                    
                authors = work.get('authorships', [])
                
                # Get all author pairs from this paper
                author_ids = []
                for author in authors:
                    author_id = author.get('author', {}).get('id')
                    if not author_id:
                        continue
                        
                    author_ids.append(author_id)
                    
                    # Update author metadata
                    if author_id not in author_metadata:
                        # Safely get institution information
                        institutions = author.get('institutions', [])
                        institution_name = ''
                        if institutions and len(institutions) > 0:
                            institution_name = institutions[0].get('display_name', '')
                        
                        author_metadata[author_id] = {
                            'name': author.get('author', {}).get('display_name', ''),
                            'orcid': author.get('author', {}).get('orcid', ''),
                            'institution': institution_name
                        }
                    
                    # Update publication count
                    author_pubs[author_id] += 1
                
                # Update co-authorship frequencies
                for i in range(len(author_ids)):
                    for j in range(i + 1, len(author_ids)):
                        pair = tuple(sorted([author_ids[i], author_ids[j]]))
                        coauthor_freq[pair] += 1
                
                papers_processed += 1
                pbar.update(1)
            
            # Get next page
            next_cursor = response.get('meta', {}).get('next_cursor')
            if not next_cursor:
                break
            params['cursor'] = next_cursor
        
        pbar.close()
        
        # Build the graph with progress bar
        self.logger.info("Building network graph...")
        G = nx.Graph()
        
        # Add nodes with metadata
        for node_id in tqdm(author_metadata.keys(), desc="Adding nodes"):
            metadata = author_metadata[node_id]
            G.add_node(node_id, 
                      name=metadata['name'],
                      orcid=metadata['orcid'],
                      institution=metadata['institution'],
                      publications=author_pubs[node_id])
        
        # Add edges with weights
        for (author1, author2), weight in tqdm(coauthor_freq.items(), desc="Adding edges"):
            G.add_edge(author1, author2, weight=weight)
        
        self.graph = G
        return G

    def visualize_network(self, min_edge_weight: int = 1) -> go.Figure:
        """
        Create an interactive visualization of the co-authorship network
        
        Args:
            min_edge_weight (int): Minimum number of collaborations to show edge
            
        Returns:
            go.Figure: Plotly figure object
        """
        if not self.graph:
            raise ValueError("No graph available. Run build_coauthorship_network first.")
        
        # Filter edges by weight
        filtered_graph = nx.Graph()
        for u, v, data in self.graph.edges(data=True):
            if data['weight'] >= min_edge_weight:
                filtered_graph.add_edge(u, v, weight=data['weight'])
        
        # Add nodes from filtered edges
        for node in filtered_graph.nodes():
            filtered_graph.nodes[node].update(self.graph.nodes[node])
        
        # Calculate layout
        pos = nx.spring_layout(filtered_graph, k=1/np.sqrt(len(filtered_graph.nodes())), iterations=50)
        
        # Create edges trace
        edge_x = []
        edge_y = []
        edge_weights = []
        
        for edge in filtered_graph.edges(data=True):
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            edge_weights.extend([edge[2]['weight'], edge[2]['weight'], None])
        
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=1, color='#888'),
            hoverinfo='none',
            mode='lines')
        
        # Create nodes trace
        node_x = []
        node_y = []
        node_text = []
        node_size = []
        
        for node in filtered_graph.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            
            # Create hover text
            node_data = filtered_graph.nodes[node]
            hover_text = (f"Name: {node_data['name']}<br>"
                         f"Publications: {node_data['publications']}<br>"
                         f"Institution: {node_data['institution']}")
            if node_data['orcid']:
                hover_text += f"<br>ORCID: {node_data['orcid']}"
            
            node_text.append(hover_text)
            node_size.append(5 + node_data['publications'])
        
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers',
            hoverinfo='text',
            text=node_text,
            marker=dict(
                showscale=True,
                size=node_size,
                colorscale='YlGnBu',
                line_width=2))
        
        # Create figure
        fig = go.Figure(data=[edge_trace, node_trace],
                       layout=go.Layout(
                           title='Co-authorship Network',
                           showlegend=False,
                           hovermode='closest',
                           margin=dict(b=20,l=5,r=5,t=40),
                           xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                           yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)))
        
        return fig

    def get_network_stats(self) -> Dict:
        """
        Calculate and return network statistics
        
        Returns:
            Dict: Dictionary containing network statistics
        """
        if not self.graph:
            raise ValueError("No graph available. Run build_coauthorship_network first.")
        
        stats = {
            'num_nodes': self.graph.number_of_nodes(),
            'num_edges': self.graph.number_of_edges(),
            'density': nx.density(self.graph),
            'avg_clustering': nx.average_clustering(self.graph),
            'avg_degree': sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes()
        }
        
        # Calculate degree centrality for top authors
        degree_cent = nx.degree_centrality(self.graph)
        top_authors = sorted(degree_cent.items(), key=lambda x: x[1], reverse=True)[:10]
        
        stats['top_authors'] = [
            {
                'name': self.graph.nodes[author_id]['name'],
                'centrality': centrality,
                'publications': self.graph.nodes[author_id]['publications']
            }
            for author_id, centrality in top_authors
        ]
        
        return stats

    def visualize_network_top_n(self, n: int = 20, min_edge_weight: int = 1) -> go.Figure:
        """
        Create an interactive visualization of the co-authorship network for top N authors
        
        Args:
            n (int): Number of top authors to include
            min_edge_weight (int): Minimum number of collaborations to show edge
            
        Returns:
            go.Figure: Plotly figure object
        """
        if not self.graph:
            raise ValueError("No graph available. Run build_coauthorship_network first.")
        
        # Get top N authors by publication count
        author_pubs = {node: data['publications'] 
                      for node, data in self.graph.nodes(data=True)}
        top_authors = sorted(author_pubs.items(), 
                           key=lambda x: x[1], 
                           reverse=True)[:n]
        top_author_ids = {author[0] for author in top_authors}
        
        # Create subgraph with only top N authors
        filtered_graph = self.graph.subgraph(top_author_ids).copy()
        
        # Filter edges by weight
        for u, v, data in list(filtered_graph.edges(data=True)):
            if data['weight'] < min_edge_weight:
                filtered_graph.remove_edge(u, v)
        
        # Calculate layout
        pos = nx.spring_layout(filtered_graph, k=1/np.sqrt(len(filtered_graph.nodes())), iterations=50)
        
        # Create edges trace
        edge_x = []
        edge_y = []
        edge_text = []
        
        for u, v, data in filtered_graph.edges(data=True):
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            
            # Add edge hover text
            weight = data['weight']
            author1 = filtered_graph.nodes[u]['name']
            author2 = filtered_graph.nodes[v]['name']
            edge_text.extend([f"{author1} - {author2}<br>Co-authored {weight} papers", "", ""])
        
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=1, color='#888'),
            hoverinfo='text',
            text=edge_text,
            mode='lines')
        
        # Create nodes trace
        node_x = []
        node_y = []
        node_text = []
        node_size = []
        node_colors = []
        
        for node in filtered_graph.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            
            # Create hover text
            node_data = filtered_graph.nodes[node]
            hover_text = (f"Name: {node_data['name']}<br>"
                         f"Publications: {node_data['publications']}<br>"
                         f"Institution: {node_data['institution']}")
            if node_data['orcid']:
                hover_text += f"<br>ORCID: {node_data['orcid']}"
            
            node_text.append(hover_text)
            node_size.append(20 + node_data['publications'] * 2)  # Increased base size
            
            # Color based on publication count
            node_colors.append(node_data['publications'])
        
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            hoverinfo='text',
            text=node_text,
            marker=dict(
                showscale=True,
                size=node_size,
                colorscale='Viridis',
                color=node_colors,
                colorbar=dict(
                    title='Publications',
                    thickness=15,
                    x=0.9
                ),
                line_width=2))
        
        # Create figure
        fig = go.Figure(data=[edge_trace, node_trace],
                       layout=go.Layout(
                           title=f'Top {n} Authors Co-authorship Network',
                           showlegend=False,
                           hovermode='closest',
                           margin=dict(b=20,l=5,r=5,t=40),
                           xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                           yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                           plot_bgcolor='white'))
        
        return fig

    def save_network_data(self, calculate_centrality: bool = False):
        """
        Save network data to CSV files and generate metadata
        
        Args:
            calculate_centrality (bool): Whether to calculate centrality measures 
                                       (can be slow for large networks)
        """
        if not self.graph:
            raise ValueError("No graph available. Run build_coauthorship_network first.")
        
        self.logger.info("Saving network data...")
        
        # Calculate basic node metrics
        node_degrees = dict(self.graph.degree())
        
        # Calculate centrality measures only if requested and network is not too large
        centrality_metrics = {}
        if calculate_centrality and self.graph.number_of_nodes() < 1000:
            self.logger.info("Calculating centrality measures (this may take a while)...")
            with tqdm(total=2, desc="Computing network metrics") as pbar:
                # Degree centrality is fast, so we'll keep it
                centrality_metrics['degree_cent'] = nx.degree_centrality(self.graph)
                pbar.update(1)
                
                # Use approximate betweenness for larger networks
                if self.graph.number_of_nodes() > 500:
                    # Sample 10% of nodes for betweenness calculation
                    k = int(0.1 * self.graph.number_of_nodes())
                    centrality_metrics['bet_cent'] = nx.betweenness_centrality(self.graph, k=k)
                else:
                    centrality_metrics['bet_cent'] = nx.betweenness_centrality(self.graph)
                pbar.update(1)
        
        # Save node data
        self.logger.info("Saving node data...")
        node_file = os.path.join(self.output_dir, 'author_nodes.csv')
        with open(node_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Adjust headers based on available metrics
            headers = ['author_id', 'name', 'institution', 'publications', 'orcid', 'degree']
            if calculate_centrality:
                headers.extend(['degree_centrality', 'betweenness_centrality'])
            
            writer.writerow(headers)
            
            for node in tqdm(self.graph.nodes(), desc="Writing node data"):
                row = [
                    node,
                    self.graph.nodes[node]['name'],
                    self.graph.nodes[node]['institution'],
                    self.graph.nodes[node]['publications'],
                    self.graph.nodes[node]['orcid'],
                    node_degrees[node]
                ]
                
                if calculate_centrality:
                    row.extend([
                        centrality_metrics['degree_cent'][node],
                        centrality_metrics['bet_cent'][node]
                    ])
                
                writer.writerow(row)
        
        # Save edge data
        self.logger.info("Saving edge data...")
        edge_file = os.path.join(self.output_dir, 'coauthorship_edges.csv')
        with open(edge_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['author1_id', 'author1_name', 'author2_id', 'author2_name', 
                           'collaboration_strength', 'author1_institution', 'author2_institution'])
            
            for u, v, data in tqdm(self.graph.edges(data=True), desc="Writing edge data"):
                writer.writerow([
                    u, self.graph.nodes[u]['name'],
                    v, self.graph.nodes[v]['name'],
                    data['weight'],
                    self.graph.nodes[u]['institution'],
                    self.graph.nodes[v]['institution']
                ])
        
        # Generate metadata file
        self.logger.info("Generating metadata...")
        metadata_file = os.path.join(self.output_dir, 'network_metadata.txt')
        with open(metadata_file, 'w', encoding='utf-8') as f:
            f.write("Co-authorship Network Metadata\n")
            f.write("============================\n\n")
            
            stats = self.get_network_stats()
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Number of authors: {stats['num_nodes']}\n")
            f.write(f"Number of co-authorship links: {stats['num_edges']}\n")
            f.write(f"Network density: {stats['density']:.3f}\n")
            f.write(f"Average degree: {stats['avg_degree']:.2f}\n\n")
            
            # Top authors by degree
            top_authors = sorted([(node, self.graph.nodes[node]['publications'], node_degrees[node]) 
                                for node in self.graph.nodes()],
                               key=lambda x: x[1], reverse=True)[:10]
            
            f.write("Top 10 Authors by Publications:\n")
            for author_id, pubs, degree in top_authors:
                f.write(f"- {self.graph.nodes[author_id]['name']}: "
                       f"{pubs} publications, {degree} collaborators\n")
            
            # Institution statistics
            institutions = [self.graph.nodes[node]['institution'] 
                          for node in self.graph.nodes()]
            unique_institutions = set(institutions)
            f.write(f"\nNumber of unique institutions: {len(unique_institutions)}\n")

    def create_multiple_network_views(self, 
                                    sizes: List[int] = [10, 20, 50], 
                                    min_edge_weight: int = 1) -> Dict[str, go.Figure]:
        """Create multiple network views and save them in the output directory"""
        network_views = {}
        for n in tqdm(sizes, desc="Creating network visualizations"):
            fig = self.visualize_network_top_n(n, min_edge_weight)
            filename = os.path.join(self.output_dir, f'coauthorship_network_top_{n}.html')
            fig.write_html(filename)
            network_views[f'top_{n}_authors'] = fig
        return network_views

def main():
    """Example usage"""
    # Initialize graph builder
    graph_builder = CoAuthorshipGraph(email="ahanmr98@gmail.com")
    
    # Build network for an institution
    G = graph_builder.build_coauthorship_network(
        institution_id="I97018004",
        start_year=2022,
        end_year=2023,
        max_papers=500
    )
    
    # Save network data and metadata
    graph_builder.save_network_data()
    
    # Create multiple network views
    network_views = graph_builder.create_multiple_network_views(
        sizes=[10, 20, 50],
        min_edge_weight=2
    )
    
    # Clean graph for GEXF export by replacing None values
    G_clean = G.copy()
    for node, data in G_clean.nodes(data=True):
        for key, value in data.items():
            if value is None:
                G_clean.nodes[node][key] = ""  # Replace None with empty string
    
    # Save cleaned network in GEXF format for Gephi
    nx.write_gexf(G_clean, os.path.join(graph_builder.output_dir, 'coauthorship_network.gexf'))
    
    print(f"\nAll files have been saved in the '{graph_builder.output_dir}' directory:")
    print("1. author_nodes.csv - Node-level data with basic metrics")
    print("2. coauthorship_edges.csv - Edge data with collaboration strengths")
    print("3. network_metadata.txt - Network statistics and metadata")
    print("4. coauthorship_network.gexf - Network file for Gephi")
    print("5. coauthorship_network_top_*.html - Interactive visualizations")
    print("6. graph_generation.log - Processing log")

if __name__ == "__main__":
    main()
