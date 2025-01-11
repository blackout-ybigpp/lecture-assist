from langchain_openai import ChatOpenAI
from langchain.schema import Document
from dotenv import load_dotenv
from langchain_aws import ChatBedrock
from sqlalchemy import create_engine, text
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import networkx as nx

load_dotenv()


# Initialize the LLM
llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    model_kwargs=dict(temperature=0.5),
    region_name='us-east-1'
    )

# Configure Korean font for matplotlib
font_path = "/home/ubuntu/RAG/font/NanumBarunGothicBold.otf"
font_prop = fm.FontProperties(fname=font_path)
plt.rcParams['font.family'] = font_prop.get_name()
plt.rcParams['axes.unicode_minus'] = False

# Initial state
accumulated_transcript = ""
current_topic = None  # To store the last identified topic

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
        # font_family=font_prop.get_name(),
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
    plt.savefig('plot.png')

def detect_and_summarize(transcript, new_text):
    """
    Analyze the transcript to determine topic transitions and provide summaries if detected.
    """
    global accumulated_transcript, current_topic

    # Add the new text to the accumulated transcript
    accumulated_transcript += f" {new_text}"

    # Prompt for topic detection and summarization
    prompt = f"""
You are an AI assistant specializing in real-time lecture summarization. 
Your primary goal is to create a hierarchical summary of the accumulated transcript whenever a topic or subtopic transition is detected. 
**Always respond in the user's language** and ensure that the summary is provided in a **keyword-based format suitable for mind map creation**.

### Input:
Accumulated Transcript: {accumulated_transcript}
New Transcript: {new_text}

### Output:
1. **Topic Transition Detection**:
   - **True/False**:
     - True: Summarize the accumulated transcript in a **keyword-based format** and restart tracking with the new transcript.
     - False: Wait for more input without generating a summary.

2. **Summary** (Only if True):
   - Provide a **hierarchical, keyword-based summary** of the accumulated transcript in the following format:
     - **Main topics** as top-level keywords.
     - **Subtopics** and details as indented bullet points under each main topic.

   Example:
   - **Machine Learning**:
     - Algorithms: supervised, unsupervised
     - Applications: recommendation systems, image recognition
   - **Neural Networks**:
     - Basics: perceptrons, deep learning
     - Features: activation functions

3. **Response Format**:
   - If False: Output **False**.
   - If True:
     - Provide the hierarchical, keyword-based summary.
     - Add **"Reset tracking"** at the end to indicate the system should restart tracking with the new transcript.

### Examples:

#### Example 1:
- **Accumulated Transcript**: "Machine learning uses algorithms like supervised and unsupervised learning."
- **New Transcript**: "Now, let’s explore neural networks and their architecture."
- **Output**:
  - **True**
  - **Summary**:
    - **Machine Learning**:
      - Algorithms: supervised, unsupervised
      - Applications: recommendation systems, image recognition
    - **Neural Networks**:
      - Basics: perceptrons, deep learning
      - Features: activation functions
  - Reset tracking.

#### Example 2:
- **Accumulated Transcript**: "The lecture focused on the benefits of solar energy."
- **New Transcript**: "Additionally, solar panels are becoming more affordable."
- **Output**:
  - **False**

### Response Guidelines:
- Respond **only in the language** used in the provided transcript.
- Ensure all summaries use **keywords and hierarchical bullet points**, not full sentences.
- If the transcript does not indicate a topic transition, output **"False"**.

"""


    response = llm.invoke(prompt)

    # Extract response text
    response_text = response.content.strip()

    # Parse response
    if response_text.startswith("True"):
        # Extract the summary and reset the transcript
        summary_start = response_text.find("- ") + 2
        summary = response_text[summary_start:].strip()

        # Reset accumulated transcript
        accumulated_transcript = ""
        return "True", summary
    elif response_text.startswith("False"):
        return "False", None
    else:
        raise ValueError("Unexpected response format from the AI.")


import json  # JSON 직렬화를 위해 추가
from sqlalchemy import create_engine, text

def save_summary_to_db(postgres_url, table_name, summary, metadata=None):
    """
    요약 내용을 데이터베이스에 저장합니다.
    """
    engine = create_engine(postgres_url)
    with engine.connect() as connection:
        query = text(f"""
            INSERT INTO {table_name} (content, metadata)
            VALUES (:content, :metadata)
        """)
        connection.commit()
        connection.execute(query, {
            "content": summary,
            "metadata": json.dumps(metadata or {})  # dict를 JSON 문자열로 변환
        })
        print(f"Summary saved to '{table_name}': {summary}")
        connection.commit()



def main():
    load_dotenv()

    postgres_url = "postgresql://postgres:blackout-26+@blackout-26-2.cj24wem202yj.us-east-1.rds.amazonaws.com:5432/postgres"
    table_name = "summary"

    print("Starting lecture summarization. Type 'exit' to quit.")
    
    while True:
        new_text = input("Enter new lecture text: ").strip()
        if new_text.lower() == "exit":
            print("Exiting summarization.")
            break
        try:
            result, summary = detect_and_summarize(accumulated_transcript, new_text)
            if result == "True":
                print(f"Topic transition detected. Summary:\n{summary}")
                print("Generating Visualization...")
                # visualization
                graph = parse_structure_to_graph(summary)
                visualize_graph(graph)
            else:
                print("No topic transition detected. Waiting for more input.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
