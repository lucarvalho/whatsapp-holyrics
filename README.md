# WhatsApp → Holyrics

Sistema de automação para recebimento de mídias pelo WhatsApp e processamento automático para utilização no Holyrics.

O projeto utiliza a WhatsApp Cloud API, um webhook em FastAPI, Docker e um Raspberry Pi como servidor intermediário. Os arquivos recebidos são processados e encaminhados para um computador Windows onde o Holyrics está instalado.

## Arquitetura

```text
WhatsApp
   │
   │ WhatsApp Cloud API
   ▼
Cloudflare Tunnel
   │
   ▼
FastAPI / Webhook
   │
   ▼
Raspberry Pi
   │
   ├── Processamento
   ├── Fila de arquivos
   └── Download do YouTube
   │
   ▼
Compartilhamento SMB
   │
   ▼
Windows
   │
   ▼
Holyrics

Funcionalidades

O sistema disponibiliza um menu pelo WhatsApp para selecionar o tipo de conteúdo que será enviado ao Holyrics.

Menu de mídias
Vídeo
Imagem
Documento
Áudio
YouTube
Vídeos

Recebe vídeos enviados pelo WhatsApp e os encaminha para o computador Windows.

Imagens

Recebe imagens pelo WhatsApp e encaminha automaticamente para o diretório de entrada do Holyrics.

Documentos

Permite o recebimento de documentos, como arquivos utilizados em apresentações.

Áudios

Recebe arquivos de áudio pelo WhatsApp e os encaminha para o Holyrics.

YouTube

O usuário pode selecionar a opção YouTube e enviar um link.

O sistema utiliza yt-dlp para realizar o download e prioriza formatos compatíveis com o ambiente utilizado pelo Holyrics:

Vídeo H.264 / AVC
Áudio AAC
Resolução de até 720p
Saída em MP4

O progresso do download pode ser acompanhado pela interface web.

Fluxo de envio

O fluxo principal pelo WhatsApp é:

4 - Envio de Mídias
        │
        ├── 1 - Vídeo
        ├── 2 - Imagem
        ├── 3 - Documento
        ├── 4 - Áudio
        └── 5 - YouTube

Após o recebimento de uma mídia, o sistema envia uma confirmação ao usuário.

No caso do YouTube, após a conclusão do download é enviada uma mensagem informando que o vídeo foi baixado e está sendo processado pelo Holyrics.

Componentes
Raspberry Pi

O servidor intermediário utiliza:

Raspberry Pi
DietPi
Docker
Docker Compose
Python
FastAPI
Uvicorn
yt-dlp
FFmpeg
WhatsApp

A integração utiliza a:

WhatsApp Cloud API

O webhook recebe as mensagens enviadas ao número configurado na plataforma da Meta.

Cloudflare

O webhook pode ser disponibilizado externamente através de um Cloudflare Tunnel.

Exemplo de arquitetura:

Internet
   │
   ▼
Cloudflare Tunnel
   │
   ▼
Raspberry Pi:8080
Windows

O computador Windows disponibiliza um compartilhamento SMB utilizado pelo Raspberry Pi para transferir os arquivos.

O diretório de entrada utilizado pelo projeto é:

C:\Holyrics\Entrada

Os arquivos transferidos podem então ser utilizados pelo Holyrics.

Docker

O projeto possui dois serviços principais:

holyrics-api

Responsável por:

API FastAPI
Webhook do WhatsApp
Interface web
Recebimento de arquivos
Download do YouTube
holyrics-worker

Responsável pelo processamento da fila de arquivos e transferência para o Windows.

A estrutura básica é:

docker-compose.yml
        │
        ├── holyrics-api
        │
        └── holyrics-worker
Estrutura do projeto
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
        ├── index.html
        ├── media_list.html
        └── presentation_list.html
Variáveis de ambiente

As configurações sensíveis são armazenadas em um arquivo .env.

O repositório disponibiliza um modelo:

.env.example

As variáveis utilizadas atualmente são:

HOLYRICS_USER=seu_usuario
HOLYRICS_PASSWORD=sua_senha

WHATSAPP_ACCESS_TOKEN=seu_token_da_meta
WHATSAPP_PHONE_NUMBER_ID=seu_phone_number_id
Segurança

O arquivo .env não deve ser enviado para o GitHub.

Tokens da Meta, senhas e credenciais de compartilhamento SMB nunca devem ser armazenados no código-fonte.

O .gitignore do projeto já está configurado para impedir o versionamento desses arquivos.

Instalação

Clone o repositório:

git clone <URL_DO_REPOSITORIO>
cd holyrics

Crie o arquivo de configuração:

cp .env.example .env

Edite o arquivo:

nano .env

Preencha as variáveis com os valores da instalação.

Depois construa e inicialize os containers:

docker compose build
docker compose up -d

Verifique os containers:

docker compose ps

Visualize os logs:

docker compose logs -f
Diretórios de dados

Durante a execução, o sistema utiliza diretórios para organizar os arquivos recebidos e processados.

Entre eles:

data/
├── incoming/
├── processing/
├── approved/
├── error/
├── youtube/
├── images/
├── videos/
├── presentations/
└── audio/

Esses diretórios não fazem parte do repositório GitHub.

Compartilhamento Windows

O Raspberry Pi utiliza SMB/CIFS para acessar o diretório compartilhado no Windows.

Exemplo:

Windows
C:\Holyrics\Entrada

        │ SMB
        ▼

Raspberry Pi
/mnt/holyrics-entrada

As credenciais do compartilhamento devem ser armazenadas separadamente e nunca devem ser publicadas no GitHub.

Compatibilidade de vídeos

Durante o desenvolvimento foi identificado que alguns vídeos do YouTube podem ser disponibilizados em codecs que não são adequados ao ambiente utilizado pelo Holyrics.

Por esse motivo, o download utiliza preferência por:

H.264 / AVC
AAC
MP4

com resolução de até 720p.

Backup

Antes de alterações importantes, recomenda-se realizar um backup da configuração do projeto.

Os arquivos de configuração podem ser armazenados separadamente das mídias e dos logs.

Não devem ser publicados no GitHub:

tokens
senhas
credenciais SMB
arquivos .env
mídias recebidas
logs
backups locais
Status do projeto

O fluxo principal de automação está funcionando:

 WhatsApp Cloud API
 Webhook
 Menu interativo
 Recebimento de vídeos
 Recebimento de imagens
 Recebimento de documentos
 Recebimento de áudios
 Download de vídeos do YouTube
 Conversão/download em formato compatível
 Fila de processamento
 Transferência para Windows
 Integração com o diretório utilizado pelo Holyrics
 Mensagens de confirmação pelo WhatsApp
 Docker / Docker Compose
Objetivo

O objetivo do projeto é simplificar o envio e a disponibilização de mídias para utilização durante os cultos, permitindo que arquivos sejam recebidos pelo WhatsApp e automaticamente encaminhados para o ambiente utilizado pelo Holyrics.

Licença

Este projeto pode ser utilizado como base para estudos, automação e integração entre WhatsApp, servidores Linux, Windows e Holyrics.

Defina uma licença adequada ao projeto antes de distribuir ou reutilizar o código em outros ambientes.
