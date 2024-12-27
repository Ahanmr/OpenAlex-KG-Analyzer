import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import networkx as nx
import numpy as np

# Generate placeholder network visualization
def create_network_placeholder():
    G = nx.random_geometric_graph(20, 0.3)
    pos = nx.spring_layout(G)
    
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    node_x = [pos[node][0] for node in G.nodes()]
    node_y = [pos[node][1] for node in G.nodes()]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode='lines', line=dict(color='#888'), hoverinfo='none'))
    fig.add_trace(go.Scatter(x=node_x, y=node_y, mode='markers', marker=dict(size=15)))
    
    fig.update_layout(title='Institution Collaboration Network', showlegend=False)
    fig.write_image("docs/images/network_example.png")

# Generate placeholder map visualization
def create_map_placeholder():
    df = pd.DataFrame({
        'country': ['USA', 'GBR', 'DEU', 'FRA', 'JPN'],
        'value': [100, 80, 60, 40, 20]
    })
    
    fig = px.choropleth(df, locations='country', locationmode='ISO-3',
                       color='value', color_continuous_scale='Viridis',
                       title='Global Collaboration Distribution')
    fig.write_image("docs/images/map_example.png")

# Generate placeholder trends visualization
def create_trends_placeholder():
    years = np.arange(2020, 2024)
    countries = ['USA', 'GBR', 'DEU']
    data = []
    
    for country in countries:
        values = np.random.randint(10, 100, size=len(years))
        for year, value in zip(years, values):
            data.append({'Year': year, 'Country': country, 'Collaborations': value})
    
    df = pd.DataFrame(data)
    fig = px.line(df, x='Year', y='Collaborations', color='Country',
                  title='Collaboration Trends by Country')
    fig.write_image("docs/images/trends_example.png")

# Generate placeholder summary visualization
def create_summary_placeholder():
    fig = make_subplots(rows=2, cols=1, subplot_titles=('Top Institutions', 'Yearly Trend'))
    
    # Top institutions bar chart
    institutions = ['Univ A', 'Univ B', 'Univ C', 'Univ D', 'Univ E']
    values = np.random.randint(20, 100, size=len(institutions))
    fig.add_trace(go.Bar(x=values, y=institutions, orientation='h'), row=1, col=1)
    
    # Yearly trend line
    years = np.arange(2020, 2024)
    trend = np.random.randint(50, 150, size=len(years))
    fig.add_trace(go.Scatter(x=years, y=trend, mode='lines+markers'), row=2, col=1)
    
    fig.update_layout(height=600, title_text="Collaboration Summary")
    fig.write_image("docs/images/summary_example.png")

if __name__ == "__main__":
    create_network_placeholder()
    create_map_placeholder()
    create_trends_placeholder()
    create_summary_placeholder()
    print("Placeholder images generated in docs/images/") 