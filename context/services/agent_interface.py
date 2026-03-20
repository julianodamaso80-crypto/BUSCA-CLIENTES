"""
Agent Interface Service.

Provides the interface between the context system and AI agents.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .query_engine import QueryEngine, ContextBlock
from ..utils.logger import get_logger


class Confidence(Enum):
    """Confidence levels for responses."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class Source:
    """A source reference for citations."""
    id: int
    file: str
    section: str
    lines: str
    relevance: float


@dataclass
class GroundedResponse:
    """A response grounded in context."""
    answer: str
    confidence: Confidence
    confidence_reason: str
    sources: List[Source]
    context_used: str
    missing_context: Optional[Dict[str, Any]] = None
    suggested_queries: List[str] = field(default_factory=list)


class AgentInterface:
    """
    Interface for AI agents to interact with the context system.

    Provides:
    - Context retrieval for queries
    - Response grounding and validation
    - Citation generation
    - Confidence assessment
    """

    SYSTEM_PROMPT = """Voce e um assistente especializado no SaaS "BUSCA CLIENTES".

REGRAS OBRIGATORIAS:
1. Responda APENAS com base no contexto fornecido abaixo
2. Se a informacao NAO estiver no contexto, diga claramente: "Nao encontrei essa informacao na documentacao."
3. Cite as fontes usando [1], [2], etc.
4. NAO invente informacoes
5. Se houver ambiguidade, peca clarificacao

FORMATO DA RESPOSTA:
- Resposta clara e objetiva
- Citacoes inline [1], [2] quando usar informacao de uma fonte
- Se nao houver contexto suficiente, indique o que esta faltando

CONTEXTO DISPONIVEL:
{context}

---
FONTES:
{sources}
"""

    def __init__(self, query_engine: Optional[QueryEngine] = None):
        """
        Initialize the agent interface.

        Args:
            query_engine: QueryEngine instance (creates default if None)
        """
        self.logger = get_logger()
        self.query_engine = query_engine or QueryEngine()

    def get_context_for_question(
        self,
        question: str,
        max_chunks: int = 5,
        max_tokens: int = 4000
    ) -> tuple[str, List[Source]]:
        """
        Get formatted context and sources for a question.

        Args:
            question: User question
            max_chunks: Maximum chunks to retrieve
            max_tokens: Maximum tokens in context

        Returns:
            Tuple of (formatted context, list of sources)
        """
        blocks = self.query_engine.get_context_for_agent(
            query=question,
            max_chunks=max_chunks,
            max_tokens=max_tokens
        )

        if not blocks:
            return "", []

        # Format context
        context_parts = []
        sources = []

        for i, block in enumerate(blocks, 1):
            # Add to context
            context_parts.append(
                f"[{i}] {block.content}"
            )

            # Add to sources
            sources.append(Source(
                id=i,
                file=block.source,
                section=block.section,
                lines=block.line_reference,
                relevance=block.relevance_score
            ))

        context = "\n\n".join(context_parts)

        # Format sources list
        sources_text = "\n".join([
            f"[{s.id}] {s.file} - {s.section} (linhas {s.lines})"
            for s in sources
        ])

        return context, sources

    def build_prompt(
        self,
        question: str,
        max_chunks: int = 5,
        max_tokens: int = 4000
    ) -> tuple[str, List[Source]]:
        """
        Build a complete prompt with context for an AI agent.

        Args:
            question: User question
            max_chunks: Maximum chunks
            max_tokens: Maximum tokens

        Returns:
            Tuple of (complete prompt, list of sources)
        """
        context, sources = self.get_context_for_question(
            question,
            max_chunks,
            max_tokens
        )

        if not context:
            prompt = f"""Voce e um assistente especializado no SaaS "BUSCA CLIENTES".

IMPORTANTE: Nao ha contexto disponivel na base de conhecimento para responder esta pergunta.

Responda indicando que a informacao nao foi encontrada e sugira que o usuario:
1. Reformule a pergunta
2. Verifique se existe documentacao sobre o tema
3. Entre em contato com o suporte se necessario

Pergunta do usuario: {question}"""
            return prompt, []

        sources_text = "\n".join([
            f"[{s.id}] {s.file} - {s.section} (linhas {s.lines})"
            for s in sources
        ])

        prompt = self.SYSTEM_PROMPT.format(
            context=context,
            sources=sources_text
        )

        prompt += f"\n\nPergunta do usuario: {question}"

        return prompt, sources

    def assess_confidence(
        self,
        question: str,
        context_blocks: List[ContextBlock]
    ) -> tuple[Confidence, str]:
        """
        Assess confidence level for answering a question.

        Args:
            question: User question
            context_blocks: Retrieved context blocks

        Returns:
            Tuple of (confidence level, reason)
        """
        if not context_blocks:
            return Confidence.NONE, "Nenhum contexto relevante encontrado"

        # Check relevance scores
        avg_score = sum(b.relevance_score for b in context_blocks) / len(context_blocks)
        max_score = max(b.relevance_score for b in context_blocks)

        # Check if multiple sources agree
        unique_docs = len(set(b.source for b in context_blocks))

        if max_score >= 0.85 and avg_score >= 0.7:
            if unique_docs >= 2:
                return Confidence.HIGH, "Multiplas fontes relevantes com alta similaridade"
            return Confidence.HIGH, "Fonte altamente relevante encontrada"

        if max_score >= 0.7 and avg_score >= 0.5:
            return Confidence.MEDIUM, "Contexto moderadamente relevante encontrado"

        if max_score >= 0.5:
            return Confidence.LOW, "Contexto com baixa relevancia - resposta pode ser incompleta"

        return Confidence.NONE, "Contexto insuficiente para responder com confianca"

    def validate_response(
        self,
        response: str,
        sources: List[Source]
    ) -> Dict[str, Any]:
        """
        Validate that a response is properly grounded in sources.

        Args:
            response: Generated response text
            sources: Available sources

        Returns:
            Validation result dictionary
        """
        validation = {
            "is_valid": True,
            "has_citations": False,
            "citation_count": 0,
            "missing_citations": [],
            "warnings": []
        }

        # Check for citations
        import re
        citations = re.findall(r'\[(\d+)\]', response)
        validation["citation_count"] = len(citations)
        validation["has_citations"] = len(citations) > 0

        # Verify citations reference valid sources
        valid_ids = {s.id for s in sources}
        for citation in citations:
            if int(citation) not in valid_ids:
                validation["warnings"].append(
                    f"Citacao [{citation}] nao corresponde a nenhuma fonte"
                )
                validation["is_valid"] = False

        # Check if response seems to be making claims without citations
        claim_patterns = [
            r'o sistema (faz|permite|tem)',
            r'voce pode',
            r'e possivel',
            r'funciona assim',
        ]

        for pattern in claim_patterns:
            if re.search(pattern, response.lower()):
                # Check if there's a citation nearby
                match = re.search(pattern, response.lower())
                if match:
                    # Look for citation within 100 chars
                    surrounding = response[max(0, match.start() - 50):match.end() + 100]
                    if not re.search(r'\[\d+\]', surrounding):
                        validation["missing_citations"].append(
                            f"Afirmacao sem citacao: '{match.group()}'"
                        )

        return validation

    def create_grounded_response(
        self,
        question: str,
        answer: str,
        sources: List[Source],
        context_blocks: Optional[List[ContextBlock]] = None
    ) -> GroundedResponse:
        """
        Create a fully grounded response with metadata.

        Args:
            question: Original question
            answer: Generated answer
            sources: Sources used
            context_blocks: Context blocks used

        Returns:
            GroundedResponse object
        """
        # Get context blocks if not provided
        if context_blocks is None:
            context_blocks = self.query_engine.get_context_for_agent(question)

        # Assess confidence
        confidence, confidence_reason = self.assess_confidence(question, context_blocks)

        # Validate response
        validation = self.validate_response(answer, sources)

        # Check for missing context
        missing_context = None
        if confidence == Confidence.NONE or confidence == Confidence.LOW:
            missing_context = {
                "topic": question,
                "suggested_doc": f"docs/{question.split()[0].lower()}.md",
                "coverage_gap": True
            }

        # Get suggested queries
        suggested = self.query_engine.suggest_related_queries(question)

        # Build context string for reference
        context_used = "\n---\n".join([
            f"{b.source}: {b.content[:200]}..."
            for b in context_blocks
        ]) if context_blocks else ""

        # Add validation warnings to answer if needed
        if validation["warnings"]:
            answer += "\n\n[Aviso: Algumas citacoes podem estar incorretas]"

        return GroundedResponse(
            answer=answer,
            confidence=confidence,
            confidence_reason=confidence_reason,
            sources=sources,
            context_used=context_used,
            missing_context=missing_context,
            suggested_queries=suggested
        )

    def format_response_for_user(self, response: GroundedResponse) -> str:
        """
        Format a grounded response for display to user.

        Args:
            response: GroundedResponse object

        Returns:
            Formatted string
        """
        parts = [response.answer]

        # Add confidence indicator
        confidence_emoji = {
            Confidence.HIGH: "✅",
            Confidence.MEDIUM: "⚠️",
            Confidence.LOW: "❓",
            Confidence.NONE: "❌"
        }

        parts.append(f"\n\n**Confianca**: {confidence_emoji[response.confidence]} {response.confidence.value}")
        parts.append(f"_{response.confidence_reason}_")

        # Add sources
        if response.sources:
            parts.append("\n**Fontes:**")
            for source in response.sources:
                parts.append(f"- [{source.id}] {source.file} ({source.section}, linhas {source.lines})")

        # Add suggestions if low confidence
        if response.missing_context:
            parts.append("\n**Contexto Faltando:**")
            parts.append(f"- Topico: {response.missing_context.get('topic', 'N/A')}")
            parts.append(f"- Sugestao: Criar {response.missing_context.get('suggested_doc', 'documentacao')}")

        if response.suggested_queries:
            parts.append("\n**Perguntas Relacionadas:**")
            for q in response.suggested_queries:
                parts.append(f"- {q}")

        return "\n".join(parts)

    def to_dict(self, response: GroundedResponse) -> Dict[str, Any]:
        """
        Convert GroundedResponse to dictionary for JSON serialization.

        Args:
            response: GroundedResponse object

        Returns:
            Dictionary representation
        """
        return {
            "answer": response.answer,
            "confidence": response.confidence.value,
            "confidence_reason": response.confidence_reason,
            "sources": [
                {
                    "id": s.id,
                    "file": s.file,
                    "section": s.section,
                    "lines": s.lines,
                    "relevance": s.relevance
                }
                for s in response.sources
            ],
            "missing_context": response.missing_context,
            "suggested_queries": response.suggested_queries
        }
