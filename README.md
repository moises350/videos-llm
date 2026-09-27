# videos-llm

Laboratório local e versionável para produção manual de vídeos curtos com auxílio de IA.

O projeto está na Phase 0. Neste estágio ele oferece apenas modelos de domínio, templates YAML e carregamento com validação. Não existem providers, APIs externas, FFmpeg, tracking de produção, publicação ou analytics.

## Requisitos

- Python 3.11 ou superior

## Instalação para desenvolvimento

```powershell
python -m pip install -e ".[dev]"
```

## Documentos de um projeto

- `project.yaml`: identidade e configuração técnica global.
- `brief.yaml`: intenção criativa.
- `script.yaml`: narração, diálogos e textos de tela.
- `storyboard.yaml`: duração e realização visual de cada cena.

`project.yaml` é o entrypoint. Os demais documentos são encontrados pelos nomes convencionais no mesmo diretório.

## Validação

```python
from pathlib import Path

from videos_llm.infrastructure import load_project

project = load_project(Path("path/to/project"))
print(project.project.title)
```

## Testes

```powershell
python -m pytest
```

Imagens, vídeos, áudio e outputs finais não são versionados inicialmente. Git LFS não está configurado.
