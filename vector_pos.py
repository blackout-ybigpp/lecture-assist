import pandas as pd
from dotenv import load_dotenv
from langchain_postgres.vectorstores import PGVector
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document
import boto3        
from langchain_aws import BedrockEmbeddings

def load_csv_to_documents(csv_file_path):
    """
    CSV 파일을 읽어 Document 객체 리스트로 변환합니다.
    """
    df = pd.read_csv(csv_file_path)
    documents = []
    for _, row in df.iterrows():
        content = row["Note"]  # CSV의 텍스트 열 이름
        metadata = row.drop("Note").to_dict()  # 'Note' 열을 제외한 나머지 데이터를 메타데이터로 저장
        document = Document(page_content=content, metadata=metadata)
        documents.append(document)
    return documents

def add_documents_to_pgvector(postgres_url, table_name, documents, embeddings):
    """
    PGVector를 초기화하고 문서를 추가합니다.
    """
    pg_vector = PGVector(
        connection=postgres_url,
        collection_name=table_name,
        embeddings=embeddings
    )
    pg_vector.add_documents(documents)
    print(f"Default collection name: {pg_vector.collection_name}")
    print(f"{len(documents)} documents added to '{table_name}'.")

def main():
    # 1. 환경 변수 로드
    load_dotenv()

    # 2. PostgreSQL 연결 정보
    postgres_url = "postgresql://postgres:blackout-26+@blackout-26-2.cj24wem202yj.us-east-1.rds.amazonaws.com:5432/postgres"
    table_name = "vector_store"
    csv_file_path = "0911_notes.csv"

    # 3. CSV 데이터를 Document로 변환
    documents = load_csv_to_documents(csv_file_path)

    # 4. LangChain 임베딩 초기화
    # embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    bedrock = boto3.client(service_name='bedrock-runtime', region_name='us-east-1')
    embeddings = BedrockEmbeddings(model_id='amazon.titan-embed-text-v1', client=bedrock)

    # 5. Document를 PGVector에 추가
    add_documents_to_pgvector(postgres_url, table_name, documents, embeddings)

if __name__ == "__main__":
    main()
