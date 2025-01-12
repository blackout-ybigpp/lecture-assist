import pandas as pd
from dotenv import load_dotenv
from langchain_postgres.vectorstores import PGVector
from langchain.schema import Document
import boto3
from langchain_aws import BedrockEmbeddings

# Convert STT data to a Document
def stt_to_document(stt_data):
    """
    STT 데이터를 Document 객체로 변환합니다.
    """
    # STT 데이터를 단일 행 DataFrame으로 가정
    df = pd.DataFrame(stt_data)  # {'Note': 'text'} 형태로 STT 데이터를 받음
    documents = []
    for _, row in df.iterrows():
        content = row["Note"]  # STT 텍스트
        metadata = row.drop("Note").to_dict()  # Note를 제외한 추가 정보를 메타데이터로 저장
        document = Document(page_content=content, metadata=metadata)
        documents.append(document)
    return documents

# Add document to PGVector
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

# Main function to process STT and update database
def process_stt_and_update(stt_data, postgres_url, table_name, embeddings):
    """
    STT 데이터를 VectorDB에 실시간으로 추가합니다.
    """
    # STT 데이터를 Document로 변환
    documents = stt_to_document(stt_data)
    # Document를 VectorDB에 추가
    add_documents_to_pgvector(postgres_url, table_name, documents, embeddings)

def main():
    # 1. 환경 변수 로드
    load_dotenv()

    # 2. PostgreSQL 연결 정보
    postgres_url = "postgresql://postgres:blackout-26+@blackout-26-2.cj24wem202yj.us-east-1.rds.amazonaws.com:5432/postgres"
    table_name = "vector_store"

    # 3. LangChain 임베딩 초기화
    # embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    bedrock = boto3.client(service_name='bedrock-runtime', region_name='us-east-1')
    embeddings = BedrockEmbeddings(model_id='amazon.titan-embed-text-v1', client=bedrock)

    print("Ready to process STT data. Type 'exit' to stop.")
    while True:
        # 5. 실시간 STT 데이터 입력 받기
        user_input = input("Enter STT data (or 'exit' to quit): ").strip()
        if user_input.lower() == "exit":
            print("Exiting...")
            break

        # 예제 STT 데이터를 구성 (단일 행 DataFrame 형태로 가정)
        stt_data = [{"Note": user_input}]

        # 6. STT 데이터를 처리하고 VectorDB에 업데이트
        process_stt_and_update(stt_data, postgres_url, table_name, embeddings)

if __name__ == "__main__":
    main()
