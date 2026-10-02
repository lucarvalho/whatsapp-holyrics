# WhatsApp → Holyrics

Automação para receber mensagens e mídias pelo WhatsApp, organizar o processamento em um servidor DietPi/Raspberry Pi e disponibilizar os arquivos ao operador do Holyrics.

O serviço usa a WhatsApp Cloud API, FastAPI, Docker Compose e um compartilhamento SMB para transferir arquivos ao computador que executa o Holyrics.

## Funcionalidades

### WhatsApp

- Acesso restrito a números cadastrados como membros da igreja.
- Menu interativo para horários, escalas, eventos, envio de mídias, ofertas e busca de músicas por tema.
- Deduplicação de mensagens recebidas pelo identificador da WhatsApp Cloud API.

A lista de membros é mantida fora do repositório em `/data/config/membros.txt`: um número por linha, com código do país e DDD, somente dígitos. Linhas iniciadas por `#` são ignoradas. Se o arquivo não puder ser lido, o acesso é negado.

### Mídias e YouTube

- Recebe imagens, vídeos, documentos e áudios pelo WhatsApp.
- Organiza os arquivos recebidos e os encaminha pela fila ao compartilhamento do Windows usado pelo Holyrics.
- Baixa vídeos do YouTube em MP4, priorizando vídeo H.264/AVC, áudio AAC e resolução de até 720p.
- Disponibiliza painel web protegido por autenticação HTTP Basic para envio e consulta de arquivos e acompanhamento do download.

### Eventos

- Interpreta convites enviados como imagem com Gemini.
- Permite revisar e corrigir os dados antes do cadastro.
- Consulta e cadastra eventos por meio da integração configurada com a planilha da igreja.

O fluxo de eventos depende do módulo `eventos.py` e de suas credenciais, instalados e configurados no servidor. Esses arquivos e credenciais não são incluídos neste repositório.

### Busca de músicas por tema

- Pesquisa semanticamente as letras cadastradas no Holyrics, por exemplo, “a misericórdia e o amor de Deus”.
- Compara o vetor da consulta com o índice local e apresenta os resultados por relevância em páginas de dez músicas.

A busca requer o arquivo de índice `/data/lyrics_embeddings_gemini001.jsonl`, gerado a partir da biblioteca do Holyrics. O índice e as letras ficam nos dados locais do servidor e não são publicados neste repositório.

## Arquitetura

```text
WhatsApp Cloud API
        │
        ▼
Cloudflare Tunnel (opcional)
        │
        ▼
FastAPI / webhook — holyrics-api
        │
        ├── WhatsApp, eventos e busca temática
        ├── Arquivos e fila em /data
        └── Painel web
                 │
                 ▼
       holyrics-worker
                 │
                 ▼
       Compartilhamento SMB
                 │
                 ▼
       Computador Windows com Holyrics
```

## Estrutura versionada

```text
.
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
└── app/
    ├── main.py
    ├── queue_processor.py
    ├── queue_worker.py
    └── templates/
```

Os diretórios de dados, índices, mídias recebidas, logs e configurações locais não devem ser versionados.

## Configuração

1. Clone o repositório e entre na pasta:

   ```bash
   git clone https://github.com/lucarvalho/whatsapp-holyrics.git
   cd whatsapp-holyrics
   ```

2. Crie o arquivo de ambiente a partir do modelo:

   ```bash
   cp .env.example .env
   ```

3. Preencha o `.env` com as credenciais da instalação:

   ```dotenv
   HOLYRICS_USER=seu_usuario
   HOLYRICS_PASSWORD=sua_senha
   WHATSAPP_ACCESS_TOKEN=token_da_whatsapp_cloud_api
   WHATSAPP_PHONE_NUMBER_ID=id_do_numero_whatsapp
   VERIFY_TOKEN=token_de_verificacao_do_webhook
   GEMINI_API_KEY=chave_da_api_gemini
   ```

   `GEMINI_API_KEY` é usada para interpretar convites e gerar o vetor das consultas temáticas. O uso desses recursos depende de uma chave válida e das cotas disponíveis na API.

4. Configure o compartilhamento SMB para que o caminho `/mnt/holyrics-entrada` aponte para a pasta de entrada do Holyrics no Windows.

5. Crie `data/config/membros.txt` e inclua os números autorizados, um por linha. Exemplo de formato:

   ```text
   # Código do país + DDD + número
   5516999999999
   ```

6. Para busca temática, coloque o índice de embeddings em `data/lyrics_embeddings_gemini001.jsonl`. A geração desse índice e a extração da biblioteca do Holyrics são etapas administrativas realizadas à parte.

7. Construa e inicie os serviços:

   ```bash
   docker compose build
   docker compose up -d
   docker compose ps
   ```

A configuração de túnel, credenciais SMB, integração com planilha e eventuais volumes adicionais depende do ambiente de cada igreja.

## Serviços Docker

- **holyrics-api**: API FastAPI, webhook do WhatsApp, painel web, recebimento de arquivos e downloads do YouTube.
- **holyrics-worker**: processa a fila de arquivos e os transfere ao compartilhamento do Windows.

O webhook usa a rota `/webhook/whatsapp`; o serviço web escuta na porta `8080`.

## Segurança e dados

Nunca publique:

- `.env`, tokens, senhas ou credenciais SMB;
- a lista de membros e números de telefone;
- arquivos de letras, índices de embeddings ou mídias recebidas;
- logs, backups locais ou credenciais da integração com planilhas.

O `.gitignore` exclui configurações locais, dados e arquivos de backup. Guarde esses dados no servidor e mantenha cópias de segurança protegidas.

## Operação

Consulte o estado dos serviços:

```bash
docker compose ps
docker compose logs -f holyrics-api
docker compose logs -f holyrics-worker
```

Antes de atualizar uma instalação em uso, faça backup das configurações e dos dados locais. A publicação de código no GitHub não atualiza nem reinicia automaticamente os containers do servidor.

## Licença

Este repositório não define uma licença de distribuição. Defina uma licença adequada antes de permitir reutilização ou redistribuição do projeto.
