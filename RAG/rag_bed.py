from dotenv import load_dotenv
from langchain_postgres.vectorstores import PGVector
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from operator import itemgetter
from langchain_aws import ChatBedrock
import boto3
from langchain_aws import BedrockEmbeddings


def load_api_keys():
    # API 키를 환경변수로 관리하기 위한 설정 파일
    load_dotenv()

def initialize_pgvector(postgres_url, collection_name,embeddings):
    pg_vector = PGVector(
        connection=postgres_url,
        collection_name=collection_name,
        embeddings=embeddings
    )
    return pg_vector


def main():
    load_api_keys()
    
    postgres_url = "postgresql://postgres:blackout-26+@blackout-26-2.cj24wem202yj.us-east-1.rds.amazonaws.com:5432/postgres"
    collection_name = "vector_store"
    bedrock = boto3.client(service_name='bedrock-runtime', region_name='us-east-1')
    embeddings = BedrockEmbeddings(model_id='amazon.titan-embed-text-v1', client=bedrock)

    
    # PGVector 초기화
    pg_vector = initialize_pgvector(postgres_url, collection_name,embeddings)
    
    retriever = pg_vector.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 5,
        "lambda_mult": 0.3  # 다양성 30%, 유사도 70%
    }
)



    # 새로운 ChatPromptTemplate 생성
    rag_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an AI assistant specialized in answering questions related to live lecture content. 
Your role is to help users understand and review the lecture material in real-time, providing concise and accurate responses based solely on the content of the lecture.

###

The lecture content is updated dynamically, and you are provided with the following information:

1. **Lecture Transcript**: This contains the real-time transcribed text of the lecture.
2. **Previous Q&A History**: Questions and answers that have been exchanged during the lecture.

Use these to provide accurate and contextual answers. You should **NOT** use any external knowledge or information that is not part of the lecture transcript or Q&A history.

###

# Available Inputs:
- **Lecture Transcript**: {lecture_transcript}
- **Q&A History**: {qa_history}

###

# Guidelines for Your Response:
1. Always refer to the lecture transcript to derive your answer.
2. If relevant, use the Q&A history to enrich your response or provide continuity.
3. Keep your answers concise but ensure they are complete, including numerical data, technical terms, or important keywords.
4. If the question cannot be answered from the provided transcript or history, state that you don't have enough information.

###

# Response Format:
[Your concise and accurate answer here]

**Source** (Optional):
- Include a specific timestamp or section of the transcript, if applicable.
- Mention the Q&A history if the answer is based on it.

###

Remember:
- Provide only lecture-relevant information.
- If a question is beyond the scope of the lecture, politely decline to answer.

###

# User's Question:
{question}

# Lecture Transcript:
{lecture_transcript}

# Q&A History:
{qa_history}

# Your Answer:
"""
        ),
        MessagesPlaceholder(variable_name="qa_history"),  # Q&A 기록 추가
        ("human", "{question}"),  # 질문
        ("assistant", "{lecture_transcript}")  # 강의 내용
    ]
    )

    # LLM 설정

# LangChain의 Bedrock LLM 설정
    llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    model_kwargs=dict(temperature=0),
    region_name='us-east-1'
    )

    # 체인 생성
    rag_chain = (
        {
        "lecture_transcript": itemgetter("question") | retriever,
        "question": itemgetter("question"),
        "qa_history": itemgetter("qa_history"),
    }
        | rag_prompt
        | llm
    )
        # 세션 기록을 저장할 딕셔너리
    store = {}


    # 세션 ID를 기반으로 세션 기록을 가져오는 함수
    def get_session_history(session_ids):
        print(f"[대화 세션ID]: {session_ids}")
        if session_ids not in store:  # 세션 ID가 store에 없는 경우
            # 새로운 ChatMessageHistory 객체를 생성하여 store에 저장
            store[session_ids] = ChatMessageHistory()
        return store[session_ids]  # 해당 세션 ID에 대한 세션 기록 반환
    
    chain_with_history = RunnableWithMessageHistory(
    rag_chain,
    get_session_history,  # 세션 기록을 가져오는 함수
    input_messages_key="question",
    # 사용자의 질문이 템플릿 변수에 들어갈 key
    history_messages_key="qa_history",  # 기록 메시지의 키
)
    # 질문에 대한 응답 스트리밍
    # answer = rag_chain.stream("OTT가 뭐야?")
    # stream_response(answer)
    
    print("채팅을 시작합니다. 종료하려면 'quit' 또는 'exit'를 입력하세요.")
    
    while True:
        # 사용자 입력 받기
        question = input("\n질문을 입력하세요: ").strip()
        
        # 종료 조건 확인
        if question.lower() in ['quit', 'exit', '종료']:
            print("채팅을 종료합니다.")
            break
            
        try:
            # 응답 생성
            response = chain_with_history.invoke(
                {"question": question},
                config={"configurable": {"session_id": "abc123"}},
            )
            
            # 응답 출력
            print("\n답변:")
            print(response.content)
            
        except Exception as e:
            print(f"\n오류가 발생했습니다: {str(e)}")
            print("다시 질문해 주세요.")
if __name__ == "__main__":
    main()