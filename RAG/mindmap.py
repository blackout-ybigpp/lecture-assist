import psycopg2
from sqlalchemy import create_engine, text
from langchain_aws import ChatBedrock
import matplotlib.pyplot as plt
import networkx as nx
import os

# Database Connection
postgres_url = "postgresql://postgres:blackout-26+@blackout-26-2.cj24wem202yj.us-east-1.rds.amazonaws.com:5432/postgres"
table_name = "summary"

# LLM Initialization
llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    model_kwargs=dict(temperature=0.5),
    region_name='us-east-1'
)

# Function to Fetch Summaries from Database
def fetch_summaries_from_db(postgres_url, table_name):
    engine = create_engine(postgres_url)
    with engine.connect() as connection:
        query = text(f"SELECT content FROM {table_name}")
        result = connection.execute(query).fetchall()
        summaries = [row[0] for row in result]
    return summaries

# Function to Generate a Hierarchical Summary via LLM
def generate_hierarchical_summary(summaries):
    prompt = f"""
You are an AI assistant specializing in summarizing hierarchical content for visualization. Given a list of summaries from a database, your goal is to create a concise, hierarchical summary suitable for generating a mind map.

### Input Format:
A series of summaries collected from past lectures:
{summaries}

### Task:
1. Combine the summaries into a single, concise hierarchical summary.
   - Use **main topics** as primary nodes.
   - Use **subtopics** and details as child nodes under each main topic.
   - Maintain brevity and structure suitable for creating a mind map.

### Output Format:
A hierarchical summary structured as follows:
- **Main Topic 1**:
  - Subtopic 1: Details
  - Subtopic 2: Details
- **Main Topic 2**:
  - Subtopic 1: Details
  - Subtopic 2: Details
"""
    response = llm.invoke(prompt)
    return response.content.strip()

# Functions to Parse and Visualize Hierarchical Summary
def parse_structure_to_graph(structured_content):
    """Parse hierarchical structured content to NetworkX graph."""
    lines = structured_content.split("\n")
    G = nx.DiGraph()
    parent = None
    for line in lines:
        indent = len(line) - len(line.lstrip())
        node = line.strip("- ").strip()
        if indent == 0:  # Major topic
            parent = node
            G.add_node(node)
        else:  # Subtopic
            if parent:
                G.add_node(node)
                G.add_edge(parent, node)
    return G

def visualize_graph(G, title="Lecture Summary Visualization"):
    """Visualize the graph using NetworkX and matplotlib."""
    pos = nx.spring_layout(G, seed=42)
    plt.figure(figsize=(14, 10))
    nx.draw(
        G, pos,
        with_labels=True,
        font_family="NanumBarunGothicOTF",
        font_size=12,
        node_size=6000,
        node_color="#D8BFD8",
        edge_color="gray",
        linewidths=1.5,
        edgecolors="#6A0DAD",
        arrows=True
    )
    plt.title(title, fontsize=16)
    plt.show()
    plt.savefig('mind_map.png')

# Main Function
def mind_map():
    # Fetch summaries from database
    summaries = fetch_summaries_from_db(postgres_url, table_name)
    
    # Generate hierarchical summary
    hierarchical_summary = generate_hierarchical_summary(summaries)
    print(f"Generated Hierarchical Summary:\n{hierarchical_summary}")

    # Parse and visualize the hierarchical summary
    graph = parse_structure_to_graph(hierarchical_summary)
    visualize_graph(graph)
    file_name = "mind_map.png"
    file_path = os.path.join(os.getcwd(), file_name)
    # print(file_path)
    
    return file_path
