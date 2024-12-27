import requests
import pandas as pd
import networkx as nx
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional
import logging
from plotly.subplots import make_subplots
import numpy as np

class OpenAlexAnalyzer:
    """
    A class to analyze OpenAlex data and build knowledge graphs
    """
    
    def __init__(self, email: str):
        """
        Initialize the OpenAlex analyzer
        
        Args:
            email (str): Email for polite pool access to OpenAlex API
        """
        self.base_url = "https://api.openalex.org"
        self.email = email
        self.headers = {'User-Agent': f'mailto:{email}'}
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make a request to the OpenAlex API
        
        Args:
            endpoint (str): API endpoint to query
            params (Dict, optional): Query parameters
            
        Returns:
            Dict: JSON response from the API
        """
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            raise

    def get_institution_collaborations(self, institution_id: str, 
                                     start_year: int, 
                                     end_year: int) -> pd.DataFrame:
        """
        Get collaboration data for an institution
        
        Args:
            institution_id (str): OpenAlex ID for the institution
            start_year (int): Start year for analysis
            end_year (int): End year for analysis
            
        Returns:
            pd.DataFrame: Collaboration data
        """
        params = {
            'filter': f'institutions.id:{institution_id},'
                     f'publication_year:{start_year}-{end_year}',
            'per_page': 200,
            'cursor': '*'  # Start cursor for pagination
        }
        
        collaborations = []
        total_processed = 0
        
        try:
            while True:
                self.logger.info(f"Fetching page of results. Total processed: {total_processed}")
                response = self._make_request('works', params)
                
                self.logger.info(f"Sample of first result: {response.get('results', [])[:1]}")
                
                if not response.get('results'):
                    if total_processed == 0:
                        self.logger.warning("No results found for the given parameters")
                    break
                    
                for work in response.get('results', []):
                    for authorship in work.get('authorships', []):
                        institutions = authorship.get('institutions', [])
                        if not institutions:
                            continue
                            
                        institution = institutions[0]
                        if institution.get('id') and institution.get('id') != institution_id:
                            collaborations.append({
                                'year': work.get('publication_year'),
                                'collaborating_institution': institution.get('display_name'),
                                'country': institution.get('country_code'),
                                'work_id': work.get('id')
                            })
                
                total_processed += len(response.get('results', []))
                
                # Check for next page
                next_cursor = response.get('meta', {}).get('next_cursor')
                if not next_cursor:
                    break
                    
                params['cursor'] = next_cursor
                
            df = pd.DataFrame(collaborations)
            if df.empty:
                self.logger.warning("No collaboration data found")
                # Return empty DataFrame with expected columns
                return pd.DataFrame(columns=['year', 'collaborating_institution', 'country', 'work_id'])
                
            self.logger.info(f"Found {len(df)} collaborations")
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to get collaboration data: {e}")
            raise

    def create_collaboration_network(self, df: pd.DataFrame) -> nx.Graph:
        """
        Create a network graph from collaboration data
        
        Args:
            df (pd.DataFrame): Collaboration data
            
        Returns:
            nx.Graph: NetworkX graph object
        """
        G = nx.Graph()
        
        for _, row in df.iterrows():
            if pd.notna(row['collaborating_institution']):
                G.add_edge('Source Institution', 
                          row['collaborating_institution'],
                          year=row['year'])
        
        return G

    def visualize_collaborations_over_time(self, df: pd.DataFrame) -> go.Figure:
        """
        Create a time series visualization of collaborations
        
        Args:
            df (pd.DataFrame): Collaboration data
            
        Returns:
            go.Figure: Plotly figure object
        """
        if df.empty:
            # Create an empty figure with a message
            fig = go.Figure()
            fig.add_annotation(
                text="No data available for the selected time period",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            return fig
        
        yearly_counts = df.groupby('year').size().reset_index(name='count')
        
        fig = px.line(yearly_counts, 
                     x='year', 
                     y='count',
                     title='Collaborations Over Time',
                     labels={'year': 'Year', 'count': 'Number of Collaborations'})
        
        return fig

    def create_collaboration_map(self, df: pd.DataFrame) -> go.Figure:
        """
        Create a chloropleth map of collaborations by country using country_converter
        """
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No collaboration data available",
                             xref="paper", yref="paper",
                             x=0.5, y=0.5, showarrow=False)
            return fig
        
        try:
            import country_converter as coco
            cc = coco.CountryConverter()
            
            # Clean and prepare country data
            country_counts = df['country'].value_counts()
            country_counts = country_counts[country_counts.index != 'US']  # Remove US if needed
            country_counts = country_counts.rename_axis('country_code').reset_index(name='num_collaborations')
            
            # Convert country codes to names and ISO3
            country_counts['country_name'] = cc.pandas_convert(country_counts['country_code'], to='name_short')
            country_counts['country_code_ISO3'] = cc.pandas_convert(country_counts['country_code'], to='ISO3')
            
            # Create the choropleth map
            fig = px.choropleth(
                country_counts,
                locations='country_code_ISO3',
                locationmode='ISO-3',
                color='num_collaborations',
                hover_name='country_name',
                title='Global Collaboration Distribution',
                color_continuous_scale='Viridis',
                labels={'num_collaborations': 'Number of Collaborations'}
            )
            
            # Update layout
            fig.update_layout(
                geo=dict(
                    showframe=False,
                    showcoastlines=True,
                    projection_type='equirectangular'
                ),
                width=1000,
                height=600,
                margin={"r":0,"t":30,"l":0,"b":0}
            )
            
            # Add hover template
            fig.update_traces(
                hovertemplate="<b>Country:</b> %{hovertext}<br>" +
                             "<b>Collaborations:</b> %{z}<br><extra></extra>"
            )
            
            self.logger.info(f"Total countries found: {len(country_counts)}")
            return fig
            
        except ImportError:
            self.logger.warning("country_converter package not found. Using basic country codes.")
            return self._create_basic_collaboration_map(df)

    def create_collaboration_trends(self, df: pd.DataFrame, top_n: int = 10) -> go.Figure:
        """
        Create a line plot showing collaboration trends for top countries over time
        """
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No collaboration data available",
                             xref="paper", yref="paper",
                             x=0.5, y=0.5, showarrow=False)
            return fig
        
        try:
            import country_converter as coco
            cc = coco.CountryConverter()
            
            # Group by year and country
            country_by_year = df.groupby(['year', 'country']).size().reset_index(name='count')
            
            # Convert country codes to names
            country_by_year['country_name'] = cc.pandas_convert(country_by_year['country'], to='name_short')
            
            # Remove US collaborations if needed
            country_by_year = country_by_year[country_by_year['country'] != 'US']
            
            # Get top N countries
            top_countries = (country_by_year.groupby('country')['count']
                            .sum()
                            .sort_values(ascending=False)
                            .head(top_n)
                            .index)
            
            country_by_year_subset = country_by_year[country_by_year['country'].isin(top_countries)]
            
            # Create the line plot
            fig = px.line(
                country_by_year_subset,
                x='year',
                y='count',
                color='country_name',
                title=f'Collaboration Trends with Top {top_n} Countries',
                labels={
                    'year': 'Year',
                    'count': 'Number of Collaborations',
                    'country_name': 'Country'
                }
            )
            
            # Update layout
            fig.update_layout(
                xaxis_title="Year",
                yaxis_title="Number of Collaborations",
                legend_title="Country",
                hovermode='x unified'
            )
            
            return fig
            
        except ImportError:
            self.logger.warning("country_converter package not found. Using basic country codes.")
            return self._create_basic_trends(df, top_n)

    def _create_basic_collaboration_map(self, df: pd.DataFrame) -> go.Figure:
        """Fallback method for creating collaboration map without country_converter"""
        # Original implementation goes here
        return super().create_collaboration_map(df)

    def create_institution_network_visualization(self, df: pd.DataFrame, top_n: int = 20) -> go.Figure:
        """
        Create an interactive network visualization of collaborating institutions
        
        Args:
            df (pd.DataFrame): Collaboration data
            top_n (int): Number of top collaborating institutions to show (default: 20)
        """
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No collaboration data available",
                             xref="paper", yref="paper",
                             x=0.5, y=0.5, showarrow=False)
            return fig

        # Create network
        G = nx.Graph()
        
        # Count collaborations per institution
        collaboration_counts = df['collaborating_institution'].value_counts()
        
        # Get top N collaborating institutions
        top_institutions = collaboration_counts.head(top_n)
        
        # Add edges with weights based on number of collaborations
        for inst, count in top_institutions.items():
            if pd.notna(inst):
                G.add_edge('Source Institution', inst, weight=count)
        
        # Calculate node positions using a spring layout
        # Adjust k parameter to spread out nodes more
        pos = nx.spring_layout(G, k=1/np.sqrt(len(G.nodes())), iterations=50)
        
        # Create edges trace with varying line thickness based on weight
        edge_x = []
        edge_y = []
        edge_weights = []
        
        for edge in G.edges(data=True):
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            edge_weights.extend([edge[2].get('weight', 1), edge[2].get('weight', 1), None])
        
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
        node_color = []
        
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            
            # Add number of collaborations to node text
            if node == 'Source Institution':
                node_text.append(f"Source Institution<br>Total Collaborations: {sum(top_institutions)}")
                node_size.append(40)
                node_color.append('#ff7f0e')  # Orange for source
            else:
                collab_count = collaboration_counts[node]
                node_text.append(f"{node}<br>Collaborations: {collab_count}")
                # Size nodes based on collaboration count
                node_size.append(20 + (collab_count / top_institutions.max()) * 20)
                node_color.append('#1f77b4')  # Blue for collaborators
        
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            hoverinfo='text',
            text=node_text,
            textposition="bottom center",
            marker=dict(
                showscale=False,
                size=node_size,
                color=node_color,
                line_width=2))
        
        # Create figure
        fig = go.Figure(data=[edge_trace, node_trace],
                       layout=go.Layout(
                           title=f'Top {top_n} Collaborating Institutions Network',
                           showlegend=False,
                           hovermode='closest',
                           margin=dict(b=20,l=5,r=5,t=40),
                           xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                           yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                           plot_bgcolor='white'))
        
        # Add a note about filtering
        fig.add_annotation(
            text=f"Showing top {top_n} collaborating institutions out of {len(collaboration_counts)}",
            xref="paper", yref="paper",
            x=0, y=1.05,
            showarrow=False,
            font=dict(size=10),
            align="left"
        )
        
        return fig

    def create_collaboration_summary(self, df: pd.DataFrame) -> go.Figure:
        """
        Create a summary visualization of collaboration patterns
        """
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No collaboration data available",
                             xref="paper", yref="paper",
                             x=0.5, y=0.5, showarrow=False)
            return fig

        # Create subplots
        fig = make_subplots(rows=2, cols=1, 
                           subplot_titles=('Top Collaborating Institutions', 
                                         'Collaborations by Year'))

        # Top collaborating institutions
        top_institutions = df['collaborating_institution'].value_counts().head(10)
        fig.add_trace(
            go.Bar(x=top_institutions.values, 
                   y=top_institutions.index, 
                   orientation='h',
                   name='Collaborations'),
            row=1, col=1
        )

        # Collaborations by year
        yearly_counts = df.groupby('year').size()
        fig.add_trace(
            go.Scatter(x=yearly_counts.index, 
                      y=yearly_counts.values,
                      mode='lines+markers',
                      name='Yearly Trend'),
            row=2, col=1
        )

        # Update layout
        fig.update_layout(
            height=800,
            showlegend=False,
            title_text="Collaboration Analysis Summary"
        )

        return fig
