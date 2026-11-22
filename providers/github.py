"""/issue dos bots (Discord e Telegram): abre uma issue no GitHub do projeto."""

import aiohttp

ERRORS = {
    401: "token do GitHub inválido ou expirado",
    403: "o token não tem permissão para criar issues nesse repositório",
    404: "repositório não encontrado (ou o token não tem acesso a ele)",
    410: "as issues estão desativadas nesse repositório",
    422: "o GitHub recusou o título ou a descrição",
}


class IssueError(Exception):
    pass


def issue_body(description: str | None, author: str, origin: str) -> str:
    footer = f"_Aberta por **{author}** pelo {origin}._"
    return f"{description.strip()}\n\n---\n{footer}" if description and description.strip() else footer


async def create_issue(token: str, repo: str, title: str, body: str) -> str:
    """Cria a issue e devolve o link; IssueError com o motivo legível se falhar."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.post(
                f"https://api.github.com/repos/{repo}/issues",
                json={"title": title.strip(), "body": body},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "TeleService",
                },
            ) as response:
                if response.status == 201:
                    return (await response.json())["html_url"]
                raise IssueError(ERRORS.get(response.status, f"GitHub respondeu HTTP {response.status}"))
    except aiohttp.ClientError as exc:
        raise IssueError(f"falha de rede ao falar com o GitHub ({exc.__class__.__name__})") from exc
