import logging

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough

from config import (
    # GPT models (summary)
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL_SUMMARY,

    # Embeddings (key riêng)
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,

    # Pinecone
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
)

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self):
        self.available = False
        self.pipeline = None
        self.retriever = None

        try:
            # 1. Embeddings
            embeddings = OpenAIEmbeddings(
                model=EMBEDDING_MODEL,             # text-embedding-3-small
                openai_api_key=EMBEDDING_API_KEY,  # KEY EMBEDDING
                openai_api_base=EMBEDDING_BASE_URL # https://aiportalapi.stu-platform.live/jpe
            )

            # 2. VectorStore
            vectorstore = PineconeVectorStore(
                index_name=PINECONE_INDEX_NAME,
                embedding=embeddings,
                pinecone_api_key=PINECONE_API_KEY,
            )

            self.retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

            llm = ChatOpenAI(
                model=OPENAI_MODEL_SUMMARY,   # GPT-5-mini
                openai_api_key=OPENAI_API_KEY,
                openai_api_base=OPENAI_BASE_URL,
                temperature=0.2,
            )

            # 4. PROMPT
            prompt = PromptTemplate.from_template("""
You are a helpful assistant.
Use ONLY the provided context to answer the question.
If the answer is not found, say:
"I cannot find the answer in the stored documents."

Question:
{question}

Context:
{context}

Answer in the same language as the question.
""")

            # 5. BUILD PIPELINE
            self.pipeline = (
                RunnableParallel(
                    question=RunnablePassthrough(),
                    context=self.retriever,
                )
                | prompt
                | llm
            )

            self.available = True
            logger.info("RAGService READY (GPT key + Embedding key + Pinecone)")

        except Exception as e:
            logger.error(f"RAG init failed: {e}")
            self.available = False

    # -----------------------------------------------------
    def is_available(self):
        return self.available

    # -----------------------------------------------------
    def ask(self, question: str):
        if not self.available:
            return None

        # Run RAG pipeline
        output = self.pipeline.invoke(question)
        answer = output.content if hasattr(output, "content") else str(output)

        # Retrieve source docs
        try:
            docs = self.retriever.invoke(question)
        except:
            docs = []

        return {
            "result": answer,
            "source_documents": docs
        }

    def ask_with_priority(self, question: str, doc_id: str):
            if not self.available:
                return None

            docs = []
            
            if doc_id:
                try:
                    docs = self.retriever.vectorstore.similarity_search(
                        question,
                        k=3,
                        filter={"doc_id": doc_id}
                    )
                except:
                    pass

            if not docs:
                try:
                    docs = self.retriever.invoke(question)
                except:
                    docs = []

            context_text = "\n\n".join([d.page_content for d in docs]) or "No context available."

            prompt = f"""
        You are a helpful assistant.
        Use ONLY the following context to answer the question.
        If answer not found, say: "I cannot find the answer."

        Context:
        {context_text}

        Question:
        {question}

        Answer:
        """

            llm = ChatOpenAI(
                model=OPENAI_MODEL_SUMMARY,
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL,
                temperature=0.2,
            )

            answer = llm.invoke(prompt).content

            return {
                "result": answer,
                "source_documents": docs
            }


        
