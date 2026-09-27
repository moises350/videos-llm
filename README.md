# videos-llm

Laboratório local e versionável para conduzir a produção de vídeos curtos cena por cena até um MP4 final. O sistema registra cada tentativa de imagem, vídeo ou áudio, mantém a seleção aprovada de cada cena e monta o resultado com FFmpeg gerenciado pelo próprio projeto.

O fluxo termina no arquivo MP4. Publicação em redes sociais continua manual e não há integração com contas externas.

## Requisitos e instalação

- Python 3.11 ou superior

```powershell
python -m pip install -e ".[dev]"
```

Isso instala também o comando `videos-llm` e uma distribuição de FFmpeg usada sem depender de uma instalação global.

## Estrutura de um projeto

- `project.yaml`: identidade e configuração técnica global.
- `brief.yaml`: intenção criativa.
- `script.yaml`: narração, diálogos e textos de tela.
- `storyboard.yaml`: duração e realização visual de cada cena.
- `composition.yaml`: ordem, tratamento e mixagem dos materiais selecionados.
- `production/<cena>/production.yaml`: histórico versionado de tentativas e seleções.
- `media/`: arquivos importados, ignorados pelo Git.
- `output/`: previews e MP4 final, também ignorados pelo Git.

`project.yaml` é o ponto de entrada. Os demais documentos ficam no mesmo diretório de projeto, e os registros de produção são separados por cena.

## Fluxo cena por cena

O piloto incluído no repositório é `projects/a-casa-inteira-foi-apostada`. Para produzir a primeira cena:

```powershell
videos-llm validate projects/a-casa-inteira-foi-apostada
videos-llm production import projects/a-casa-inteira-foi-apostada scene-001 C:\media\scene-001.png --method imagegen --prompt prompts/image/scene-001.md
videos-llm production select projects/a-casa-inteira-foi-apostada scene-001 key_image asset-012345abcdef
videos-llm validate projects/a-casa-inteira-foi-apostada --production
videos-llm compose projects/a-casa-inteira-foi-apostada --preview
videos-llm compose projects/a-casa-inteira-foi-apostada
```

O comando `production import` imprime o identificador real do material criado. Substitua `asset-012345abcdef` por esse valor no comando `production select`.

Repita importação e seleção para os papéis exigidos em cada cena. Novas tentativas não apagam as anteriores: o histórico e a procedência ficam em `production.yaml`, enquanto somente a tentativa escolhida é usada na montagem. A validação com `--production` informa exatamente qual seleção ainda falta.

O preview é renderizado em 360 × 640 para validação rápida. A montagem final usa largura, altura, taxa de quadros e duração definidas pelo projeto. Ambos são gravados dentro de `output/`; o arquivo final padrão é `output/final.mp4`.

## Testes

```powershell
python -m pytest -q
python -m pip check
```

Imagens, vídeos, áudios e outputs renderizados não são versionados. Os YAMLs de produção são versionados para que as decisões criativas possam ser auditadas e retomadas.
