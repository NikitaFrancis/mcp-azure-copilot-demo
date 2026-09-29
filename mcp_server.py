import logging
import os
import sys
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError


logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("azure_ai_foundry_mcp")

server = MCPServer(
    name="azure-ai-foundry",
    description="Consulta un agente existente de Azure AI Foundry.",
)


def _format_response(response: Any) -> str:
    answer = response.output_text.strip()
    if not answer:
        return "Azure AI Foundry returned no text response."

    citations: list[str] = []
    seen: set[str] = set()
    for item in response.output:
        for content in getattr(item, "content", []):
            for annotation in getattr(content, "annotations", []):
                citation_type = getattr(annotation, "type", "")
                if citation_type == "url_citation":
                    url = getattr(annotation, "url", "")
                    title = getattr(annotation, "title", "") or url
                    citation = f"[{title}]({url})" if url else title
                elif citation_type in {"file_citation", "container_file_citation"}:
                    citation = getattr(annotation, "filename", "") or getattr(
                        annotation, "file_id", ""
                    )
                else:
                    continue

                if citation and citation not in seen:
                    seen.add(citation)
                    citations.append(citation)

    if citations:
        answer += "\n\nSources:\n" + "\n".join(f"- {item}" for item in citations)
    return answer


@server.tool(
    name="query_foundry",
    description=(
        "Consulta el agente configurado en Azure AI Foundry. Úsala para responder "
        "preguntas sobre la base de conocimiento conectada al agente."
    ),
)
def query_foundry(question: str) -> str:
    """Send a question to the configured Foundry agent and return its answer."""
    question = question.strip()
    if not question:
        raise ValueError("question must not be empty")
    if len(question) > 10_000:
        raise ValueError("question must be 10,000 characters or fewer")

    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    agent_name = os.getenv("FOUNDRY_AGENT_NAME")
    if not endpoint or not agent_name:
        raise ToolError(
            "Azure AI Foundry is not configured. Set FOUNDRY_PROJECT_ENDPOINT "
            "and FOUNDRY_AGENT_NAME."
        )

    try:
        with (
            DefaultAzureCredential() as credential,
            AIProjectClient(endpoint=endpoint, credential=credential) as project,
            project.get_openai_client(agent_name=agent_name) as openai,
        ):
            response = openai.responses.create(input=question)
    except Exception as exc:
        logger.exception("Azure AI Foundry query failed")
        raise ToolError(
            "Azure AI Foundry query failed. Check the project endpoint, agent name, "
            "Azure sign-in, and project permissions. "
            f"Error type: {type(exc).__name__}."
        ) from exc

    return _format_response(response)


if __name__ == "__main__":
    server.run(transport="stdio")