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
        # Track per-doc lightweight state so follow-up prompts ("next") stay scoped
        # and avoid mixing conversations across documents/users.
        self._history = {}

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

        normalized = (question or "").strip()
        lower_q = normalized.lower()
        is_followup = lower_q in {"next", "tiếp theo", "tiep theo", "tiếp", "tiep"}

        # Scope history by document id to avoid mixing users/sessions
        history_key = (doc_id or "").strip() or "__global__"
        state = self._history.setdefault(history_key, {"q": None, "a": None})

        if is_followup and not state["q"]:
            return {
                "result": "Chưa có câu hỏi trước đó để tiếp tục. Vui lòng đặt câu hỏi cụ thể.",
                "source_documents": [],
            }

        # When user asks for "next", reuse previous question/doc to keep context
        effective_question = state["q"] if is_followup else normalized
        effective_doc_id = doc_id or history_key if history_key != "__global__" else ""

        docs = []
        
        if effective_doc_id:
            try:
                docs = self.retriever.vectorstore.similarity_search(
                    effective_question,
                    k=3,
                    filter={"doc_id": effective_doc_id}
                )
            except:
                pass

        if not docs:
            try:
                docs = self.retriever.invoke(effective_question)
            except:
                docs = []

        context_text = "\n\n".join([d.page_content for d in docs]) or "No context available."

        followup_note = ""
        if is_followup and state["a"]:
            followup_note = (
                "\nPrevious answer (do not repeat, extend instead):\n"
                f"{state['a']}\n"
            )

        prompt = f"""
        You are a helpful assistant.
        Use ONLY the following context to answer the question.
        If answer not found, say: "I cannot find the answer."
        If this is a follow-up request like 'next', continue the previous answer with new details and avoid repetition.

        Context:
        {context_text}
        {followup_note}

        Question:
        {effective_question}

        Answer:
        """

        llm = ChatOpenAI(
            model=OPENAI_MODEL_SUMMARY,
            openai_api_key=OPENAI_API_KEY,
            openai_api_base=OPENAI_BASE_URL,
            temperature=0.2,
        )

        answer = llm.invoke(prompt).content

        # Persist lightweight state for subsequent follow-up turns
        state["q"] = effective_question
        state["a"] = answer

        return {
            "result": answer,
            "source_documents": docs
        }


        
