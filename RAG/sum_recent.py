import psycopg2
from sqlalchemy import create_engine, text
from langchain_aws import ChatBedrock
from dotenv import load_dotenv
import os

# 환경 변수 로드
load_dotenv()

# LLM 초기화
llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    model_kwargs=dict(temperature=0.5),
    region_name="us-east-1"
)

# PostgreSQL 연결 정보
postgres_url = "postgresql://postgres:blackout-26+@blackout-26-2.cj24wem202yj.us-east-1.rds.amazonaws.com:5432/postgres"
TABLE_NAME = "langchain_pg_embedding"

def fetch_recent_documents(limit=10):
    """최근 N개의 문서를 데이터베이스에서 가져옵니다."""
    engine = create_engine(postgres_url)
    query = text(f"""
        SELECT document
        FROM {TABLE_NAME}
        ORDER BY id DESC
        LIMIT :limit
    """)
    with engine.connect() as connection:
        result = connection.execute(query, {"limit": limit})
        return [row[0] for row in result]

def summarize_documents(documents):
    prompt = f"""
You are an AI assistant that summarizes a list of text documents into a concise and hierarchical summary.

### Input:
Documents:
{documents}

### Output:
Provide a hierarchical summary of the documents, grouping related topics together with sub-bullets for details.

Example Format:
- Major Topic 1:
  - Detail 1
  - Detail 2
- Major Topic 2:
  - Detail 1
  - Detail 2

### Response Guidelines:
- Respond **only in the language** used in the provided transcript.
- Ensure all summaries use **keywords and hierarchical bullet points**, not full sentences.

"""
    
    response = llm.invoke(prompt)
    return response.content.strip()

def sum_recent():
    # 최근 문서 가져오기
    recent_documents = fetch_recent_documents(limit=10)

    if not recent_documents:
        print("No recent documents found.")
        return

    # 요약 생성
    summary = summarize_documents(recent_documents)

    # 결과 출력
    return summary

