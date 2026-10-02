from fastapi import FastAPI, UploadFile, File, Form, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pathlib import Path
from collections import OrderedDict
import shutil
import html
import subprocess
import json
import logging
from urllib.parse import quote
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import os
import threading
import asyncio
import urllib.request
import re
import math
from datetime import datetime

def create_media_filename(sender_name, original_filename):
    """Cria um nome seguro e único para um arquivo recebido pelo WhatsApp."""
    sender_name = sender_name.strip()

    sender_name = re.sub(
        r'[\\/:*?"<>|]',
        '',
        sender_name
    )

    sender_name = re.sub(
        r'\s+',
        '_',
        sender_name
    )

    original_filename = Path(
        original_filename
    ).name

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    if original_filename:
        return (
            f"{sender_name}_"
            f"{timestamp}_"
            f"{original_filename}"
        )

    return (
        f"{sender_name}_"
        f"{timestamp}"
    )

app = FastAPI(title="Holyrics Media Server")

security = HTTPBasic()

AUTH_USER = os.getenv("HOLYRICS_USER")
AUTH_PASSWORD = os.getenv("HOLYRICS_PASSWORD")

youtube_progress = {
    "status": "idle",
    "percent": 0,
    "downloaded": "",
    "total": "",
}


def authenticate(credentials: HTTPBasicCredentials = Depends(security)):

    """Confere as credenciais HTTP Basic usadas para proteger o painel."""
    valid_user = secrets.compare_digest(
        credentials.username,
        AUTH_USER
    )

    valid_password = secrets.compare_digest(
        credentials.password,
        AUTH_PASSWORD
    )

    if not (valid_user and valid_password):

        raise HTTPException(
            status_code=401,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"}
        )

    return credentials.username

templates = Jinja2Templates(directory="/app/templates")

async def download_whatsapp_media(media_id, filename, sender=None, media_type=None):

    """Baixa uma mídia recebida pelo WhatsApp e salva no diretório de entrada."""
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")

    if not access_token:
        raise RuntimeError(
            "WHATSAPP_ACCESS_TOKEN não configurado."
        )

    media_api_url = (
        f"https://graph.facebook.com/v23.0/{media_id}"
    )

    request = urllib.request.Request(
        media_api_url,
        headers={
            "Authorization": f"Bearer {access_token}"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        media_info = json.loads(
            response.read().decode("utf-8")
        )

    media_url = media_info.get("url")

    if not media_url:
        raise RuntimeError(
            "Meta não retornou a URL da mídia."
        )

    safe_filename = Path(filename).name

    destination = INCOMING / safe_filename
    temporary_destination = INCOMING / f"{safe_filename}.part"

    download_request = urllib.request.Request(
        media_url,
        headers={
            "Authorization": f"Bearer {access_token}"
        }
    )

    try:

        with urllib.request.urlopen(
            download_request,
            timeout=120
        ) as response:

            with temporary_destination.open("wb") as file:
                shutil.copyfileobj(
                    response,
                    file
                )

        temporary_destination.replace(destination)



    except Exception:

        if temporary_destination.exists():
            temporary_destination.unlink()

        raise

    logging.info(
        "WHATSAPP | Mídia baixada: %s",
        safe_filename
    )



    print(
        f"📥 WHATSAPP | Mídia baixada: "
        f"{safe_filename}",
        flush=True
    )

    if media_type == "video" and sender:
        asyncio.create_task(
            send_whatsapp_message(
                sender,
                "✅ *Vídeo enviado com sucesso!*\n\n"
                "O arquivo já está sendo processado pelo Holyrics. "
                "Procure o operador de mídia para passar as instruções "
                "de uso do vídeo no culto."
            )
        )



  #  print(
  #      f"DEBUG CONDIÇÃO | media_type == image: {media_type == 'image'} | sender existe: {bool(sender)}",
  #      flush=True
  #  )


    if media_type == "audio" and sender:

        asyncio.create_task(
            send_whatsapp_message(
                sender,
                "✅ *Áudio enviado com sucesso!*\n\n"
                "O arquivo já está sendo processado pelo Holyrics."
                "Procure o operador de mídia para passar as instruções "
                "de uso do audio no culto."
            )
        )

    if media_type == "document" and sender:

        asyncio.create_task(
            send_whatsapp_message(
                sender,
                "✅ *Documento enviado com sucesso!*\n\n"
                "O arquivo já está sendo processado pelo Holyrics."
                "Procure o operador de mídia para passar as instruções "
                "de uso da apresentação no culto."
            )
        )

    if media_type == "image" and sender:

        asyncio.create_task(
            send_whatsapp_message(
                sender,
                "✅ *Imagem enviada com sucesso!*\n\n"
                "A imagem já está sendo processada pelo Holyrics."
                "Procure o operador de mídia para passar as instruções "
                "de uso da imagem no culto."
            )
        )


    return destination
    



async def download_whatsapp_event_image(media_id, filename):
    """
    Baixa uma imagem de convite enviada pelo WhatsApp
    exclusivamente para o fluxo de cadastro de eventos.

    Diferente de download_whatsapp_media(), esta função NÃO
    utiliza /data/incoming/ e portanto não envia a imagem
    para o processamento do Holyrics.
    """

    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")

    if not access_token:
        raise RuntimeError(
            "WHATSAPP_ACCESS_TOKEN não configurado."
        )

    media_api_url = (
        f"https://graph.facebook.com/v23.0/{media_id}"
    )

    request = urllib.request.Request(
        media_api_url,
        headers={
            "Authorization": f"Bearer {access_token}"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        media_info = json.loads(
            response.read().decode("utf-8")
        )

    media_url = media_info.get("url")

    if not media_url:
        raise RuntimeError(
            "Meta não retornou a URL da mídia."
        )

    safe_filename = Path(filename).name

    destination = EVENTOS / safe_filename
    temporary_destination = EVENTOS / f"{safe_filename}.part"

    download_request = urllib.request.Request(
        media_url,
        headers={
            "Authorization": f"Bearer {access_token}"
        }
    )

    try:

        with urllib.request.urlopen(
            download_request,
            timeout=120
        ) as response:

            with temporary_destination.open("wb") as file:
                shutil.copyfileobj(
                    response,
                    file
                )

        temporary_destination.replace(destination)

    except Exception:

        if temporary_destination.exists():
            temporary_destination.unlink()

        raise

    logging.info(
        "WHATSAPP | Convite de evento baixado: %s",
        safe_filename
    )

    print(
        f"📥 WHATSAPP | Convite de evento baixado: "
        f"{safe_filename}",
        flush=True
    )

    return destination



async def interpretar_convite_evento(caminho_imagem):
    """
    Envia uma imagem de convite para o Gemini e extrai
    os dados estruturados do evento.

    Esta função NÃO grava nada na planilha e NÃO envia
    mensagens ao WhatsApp.
    """

    import base64
    import json
    import requests

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não configurada."
        )

    caminho = Path(caminho_imagem)

    if not caminho.exists():
        raise FileNotFoundError(
            f"Imagem não encontrada: {caminho}"
        )

    mime_type = "image/jpeg"

    extensao = caminho.suffix.lower()

    if extensao == ".png":
        mime_type = "image/png"
    elif extensao == ".webp":
        mime_type = "image/webp"

    with caminho.open("rb") as arquivo_imagem:
        imagem = base64.b64encode(
            arquivo_imagem.read()
        ).decode("utf-8")

    prompt = """
Analise cuidadosamente esta imagem de um convite ou cartaz de evento.

Extraia somente as informações que estiverem claramente presentes na imagem.

Retorne exclusivamente um JSON válido, sem markdown e sem explicações, usando exatamente estes campos:

{
  "data": "",
  "evento": "",
  "horario": "",
  "local": "",
  "descricao": ""
}

Regras:
- data: use o formato DD/MM/AAAA.
- evento: nome ou título principal do evento.
- horario: retorne somente UM horário no formato de 24 horas HH:MM, por exemplo "19:30" ou "08:00". Nunca inclua palavras, rótulos, mais de um horário ou intervalo neste campo. Se houver um intervalo de início e término, use somente o horário de início. Se houver horários de etapas diferentes (por exemplo, velório e sepultamento), use o início da atividade principal indicada pelo título do evento; coloque os demais horários, com seus rótulos, em descricao. Se o horário principal não puder ser identificado com segurança, deixe vazio.
- local: retorne somente o local principal da atividade indicada pelo título do evento, incluindo o endereço visível desse local. Não inclua outro local usado em uma etapa secundária; registre esse outro local em descricao junto com o nome da etapa. Se o local principal não puder ser identificado com segurança, deixe vazio.
- descricao: inclua as demais informações relevantes, como tema, pregadores, palestrantes, organizadores, inscrição, contribuição e observações. Coloque também aqui, com seus rótulos, os horários secundários e locais de outras etapas; não misture esses dados nos campos horario e local.
- Separe os dados mesmo quando aparecerem juntos na mesma frase ou linha. Exemplo: em "19h30 na Igreja Central, preletor João", use "19:30" em horario, "Igreja Central" em local e "Preletor João" em descricao.
- Exemplo com etapas: se o convite disser "Velório: início às 8h00, término às 16h30; sepultamento às 17h00 no Cemitério São Pedro", use "08:00" em horario, o local principal do velório em local e "Término do velório às 16h30; sepultamento às 17h00 no Cemitério São Pedro" em descricao.
- Não invente nenhuma informação.
- Se uma informação não estiver presente ou não puder ser identificada com segurança, deixe o campo vazio.
"""

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/interactions"
    )

    payload = {
        "model": "gemini-3.8-flash",
        "input": [
            {
                "type": "image",
                "mime_type": mime_type,
                "data": imagem
            },
            {
                "type": "text",
                "text": prompt
            }
        ]
    }
    import time

    for tentativa in range(2):

        response = requests.post(
            url,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=120
        )

        if response.ok:
            break

        if response.status_code == 503 and tentativa == 0:

            logging.warning(
                "GEMINI | Serviço indisponível (503). "
                "Nova tentativa em 5 segundos."
            )

            time.sleep(5)

        else:

            raise RuntimeError(
                f"Gemini retornou HTTP {response.status_code}: "
                f"{response.text}"
            )


    resposta = response.json()

    texto_resposta = ""

    for step in resposta.get("steps", []):
        if step.get("type") == "model_output":

            for content in step.get("content", []):

                if content.get("type") == "text":
                    texto_resposta += content.get(
                        "text",
                        ""
                    )

    if not texto_resposta:
        raise RuntimeError(
            "Gemini não retornou conteúdo de texto."
        )

    texto_resposta = texto_resposta.strip()

    # Remove eventual bloco markdown caso o modelo
    # retorne ```json ... ```
    if texto_resposta.startswith("```"):
        linhas = texto_resposta.splitlines()

        if linhas and linhas[0].startswith("```"):
            linhas = linhas[1:]

        if linhas and linhas[-1].strip() == "```":
            linhas = linhas[:-1]

        texto_resposta = "\n".join(linhas).strip()

    try:
        dados = json.loads(texto_resposta)

    except json.JSONDecodeError as erro:

        raise RuntimeError(
            "Gemini retornou uma resposta que não é "
            f"JSON válido: {texto_resposta}"
        ) from erro

    campos = [
        "data",
        "evento",
        "horario",
        "local",
        "descricao"
    ]

    resultado = {}

    for campo in campos:

        valor = dados.get(campo, "")

        if valor is None:
            valor = ""

        resultado[campo] = str(valor).strip()

    logging.info(
        "GEMINI | Convite interpretado: %s",
        resultado
    )

    return resultado

def montar_mensagem_revisao_evento(dados_evento):
    """
    Monta a tela de revisão dos dados do evento.
    """

    return (
        "📅 *DADOS DO EVENTO*\n\n"
        f"1️⃣ *Data:* {dados_evento.get('data') or 'Não informado'}\n"
        f"2️⃣ *Evento:* {dados_evento.get('evento') or 'Não informado'}\n"
        f"3️⃣ *Horário:* {dados_evento.get('horario') or 'Não informado'}\n"
        f"4️⃣ *Local:* {dados_evento.get('local') or 'Não informado'}\n"
        f"5️⃣ *Descrição:* {dados_evento.get('descricao') or 'Não informado'}\n\n"
        "Escolha o número do campo que deseja alterar.\n\n"
        "6️⃣ Confirmar cadastro\n"
        "0️⃣ Cancelar"
    )


async def send_whatsapp_message(recipient, text):

    """Envia uma mensagem de texto usando a API do WhatsApp."""
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    if not access_token:
        raise RuntimeError(
            "WHATSAPP_ACCESS_TOKEN não configurado."
        )

    if not phone_number_id:
        raise RuntimeError(
            "WHATSAPP_PHONE_NUMBER_ID não configurado."
        )

    url = (
        f"https://graph.facebook.com/v23.0/"
        f"{phone_number_id}/messages"
    )

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text
        }
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            response_data = json.loads(
                response.read().decode("utf-8")
            )

        logging.info(
            "WHATSAPP | Mensagem enviada para %s",
            recipient
        )

        return response_data

    except Exception as error:

        logging.error(
            "WHATSAPP | Erro ao enviar mensagem: %s",
            error
        )

        raise



BASE = Path("/data")
MEMBERS_FILE = BASE / "config" / "membros.txt"


def is_authorized_whatsapp_sender(sender):
    """Check the current member list so edits take effect without a restart."""
    if not sender:
        return False

    sender_number = re.sub(r"\D", "", str(sender))
    if not sender_number:
        return False

    try:
        with MEMBERS_FILE.open("r", encoding="utf-8") as members_file:
            authorized_numbers = {
                re.sub(r"\D", "", line.strip())
                for line in members_file
                if line.strip() and not line.lstrip().startswith("#")
            }
    except OSError:
        logging.exception(
            "WHATSAPP | Não foi possível ler a lista de membros em %s",
            MEMBERS_FILE,
        )
        return False

    return sender_number in authorized_numbers


SONG_THEME_MODEL = "models/gemini-embedding-001"
SONG_THEME_INDEX_FILE = Path("/data/lyrics_embeddings_gemini001.jsonl")
SONG_THEME_PAGE_SIZE = 10
song_theme_index_cache = None
whatsapp_song_theme_results = {}


def load_song_theme_index():
    """Load the local song vectors once, keeping lyrics out of WhatsApp replies."""
    global song_theme_index_cache

    if song_theme_index_cache is not None:
        return song_theme_index_cache

    if not SONG_THEME_INDEX_FILE.is_file():
        raise RuntimeError("Índice de músicas não encontrado em /data.")

    songs = []
    with SONG_THEME_INDEX_FILE.open("r", encoding="utf-8") as index_file:
        for line_number, line in enumerate(index_file, 1):
            if not line.strip():
                continue

            item = json.loads(line)
            if item.get("model") != SONG_THEME_MODEL:
                raise RuntimeError(
                    f"Modelo inesperado no índice, linha {line_number}."
                )

            values = item.get("embedding") or []
            if len(values) != 3072:
                raise RuntimeError(
                    f"Vetor inválido no índice, linha {line_number}."
                )

            norm = math.sqrt(sum(value * value for value in values))
            if not norm:
                continue

            songs.append({
                "id": str(item.get("id", "")),
                "title": item.get("title", ""),
                "artist": item.get("artist", ""),
                "embedding": values,
                "norm": norm,
            })

    if not songs:
        raise RuntimeError("O índice de músicas está vazio.")

    song_theme_index_cache = songs
    logging.info("BUSCA TEMÁTICA | Índice carregado: %s músicas", len(songs))
    return song_theme_index_cache


def search_songs_by_theme(theme):
    """Embed a short search phrase and rank songs locally by cosine similarity."""
    import requests

    songs = load_song_theme_index()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não configurada.")

    payload = {
        "requests": [{
            "model": SONG_THEME_MODEL,
            "content": {"parts": [{"text": theme}]},
            "embedContentConfig": {"taskType": "RETRIEVAL_QUERY"},
        }]
    }
    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-embedding-001:batchEmbedContents",
        headers={"x-goog-api-key": api_key},
        json=payload,
        timeout=45,
    )
    response.raise_for_status()

    embeddings = response.json().get("embeddings", [])
    if len(embeddings) != 1:
        raise RuntimeError("Gemini não retornou o vetor da consulta.")

    query_vector = embeddings[0].get("values") or []
    if len(query_vector) != 3072:
        raise RuntimeError("Gemini retornou um vetor de dimensão inesperada.")

    query_norm = math.sqrt(sum(value * value for value in query_vector))
    if not query_norm:
        raise RuntimeError("Gemini retornou um vetor vazio.")

    ranked = []
    for song in songs:
        dot_product = sum(
            query_value * song_value
            for query_value, song_value in zip(
                query_vector,
                song["embedding"],
            )
        )
        score = dot_product / (query_norm * song["norm"])
        ranked.append((score, song["title"], song["artist"]))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked


def format_song_theme_page(theme, ranked, offset):
    """Formata uma página dos resultados ordenados da busca temática de músicas."""
    total = len(ranked)
    end = min(offset + SONG_THEME_PAGE_SIZE, total)
    lines = [f"🎵 MÚSICAS RELACIONADAS AO TEMA\n\nTema: {theme}\n"]

    for position, (score, title, artist) in enumerate(
        ranked[offset:end],
        start=offset + 1,
    ):
        attribution = f" — {artist}" if artist else ""
        lines.append(f"{position}. {title}{attribution}")

    lines.append(f"\nExibindo {offset + 1}–{end} de {total} músicas por relevância.")
    if end < total:
        lines.append("1️⃣ Mais resultados")
    lines.extend([
        "2️⃣ Nova consulta",
        "0️⃣ Menu principal",
    ])
    return "\n".join(lines)


whatsapp_menu_state = {}
eventos_pendentes = {}
processed_whatsapp_message_ids = OrderedDict()
WHATSAPP_MESSAGE_ID_CACHE_LIMIT = 5000

INCOMING = BASE / "incoming"
IMAGES = BASE / "images"
VIDEOS = BASE / "videos"
PRESENTATIONS = BASE / "presentations"
AUDIO = BASE / "audio"
YOUTUBE = BASE / "youtube"
ERROR = BASE / "error"
EVENTOS = BASE / "eventos"

for directory in [
    INCOMING,
    IMAGES,
    VIDEOS,
    PRESENTATIONS,
    AUDIO,
    YOUTUBE,
    ERROR
]:
    directory.mkdir(parents=True, exist_ok=True)


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".mpeg", ".mpg"
}

PRESENTATION_EXTENSIONS = {
    ".pdf", ".ppt", ".pptx"
}
AUDIO_EXTENSIONS = {
    ".mp3"
}


def classify_file(filename: str):

    """Classifica um arquivo pelo tipo indicado em sua extensão."""
    extension = Path(filename).suffix.lower()

    if extension in IMAGE_EXTENSIONS:
        return IMAGES

    if extension in VIDEO_EXTENSIONS:
        return VIDEOS

    if extension in PRESENTATION_EXTENSIONS:
        return PRESENTATIONS

    if extension in AUDIO_EXTENSIONS:
        return AUDIO

    return None

async def download_youtube(url: str, sender=None):

    """Baixa um vídeo do YouTube e acompanha o envio ao fluxo de mídia."""
    command = [
        "yt-dlp",

        "--no-playlist",

        "--print-json",

        "--newline",

        "--progress",

        "-f",
        "bv*[vcodec^=avc1][height<=720]+ba[acodec^=mp4a]/b[ext=mp4]",

        "--merge-output-format",
        "mp4",

        "-o",
        "/data/incoming/%(title)s.%(ext)s",

        url
    ]

    youtube_progress["status"] = "downloading"
    youtube_progress["percent"] = 0
    youtube_progress["downloaded"] = ""
    youtube_progress["total"] = ""

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    output_lines = []

    while True:

        line = await asyncio.to_thread(
            process.stdout.readline
        )

        if not line:
            break

        line = line.strip()

        output_lines.append(line)

        if "[download]" in line and "%" in line:

            try:

                percent_text = (
                    line.split("%")[0]
                    .split()[-1]
                )

                percent = float(percent_text)

                youtube_progress["status"] = "downloading"

                if percent > youtube_progress["percent"]:
                    youtube_progress["percent"] = percent

                print(
                    f"Progresso YouTube: {percent:.1f}%",
                    flush=True
                )

            except (ValueError, IndexError):
                pass

    await asyncio.to_thread(process.wait)

    if process.returncode != 0:

        youtube_progress["status"] = "error"

        error_output = "\n".join(output_lines)

        logging.error(
            "Erro yt-dlp WhatsApp:\n%s",
            error_output[-5000:]
        )

        print(
            f"❌ ERRO YT-DLP:\n{error_output[-5000:]}",
            flush=True
        )

        raise Exception(
            "Erro ao baixar vídeo do YouTube."
        )

    youtube_progress["status"] = "completed"
    youtube_progress["percent"] = 100

    if sender:
        asyncio.create_task(
            send_whatsapp_message(
                sender,
                "✅ *Vídeo do YouTube baixado com sucesso!*\n\n"
                "O arquivo já está sendo processado pelo Holyrics."
                "Procure o operador de mídia para passar as instruções "
                "de uso do vídeo no culto."
            )
        )

    video_info = None

    for line in output_lines:

        try:

            data = json.loads(line)

            if isinstance(data, dict) and "title" in data:
                video_info = data

        except json.JSONDecodeError:

            continue

    title = (
        video_info.get("title", "Vídeo do YouTube")
        if video_info
        else "Vídeo do YouTube"
    )

    duration = (
        video_info.get("duration", 0)
        if video_info
        else 0
    )

    mp4_files = list(INCOMING.glob("*.mp4"))

    if not mp4_files:

        raise Exception(
            "Download concluído, mas o arquivo MP4 "
            "não foi encontrado."
        )

    video_file = max(
        mp4_files,
        key=lambda p: p.stat().st_mtime
    )

    return {
        "title": title,
        "duration": duration,
        "file": video_file,
        "size": video_file.stat().st_size
    }


def format_size(size):

    """Converte um tamanho em bytes para uma representação legível."""
    if size < 1024:
        return f"{size} B"

    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"

    if size < 1024 ** 3:
        return f"{size / (1024 ** 2):.1f} MB"

    return f"{size / (1024 ** 3):.2f} GB"


def format_duration(seconds):

    """Converte uma duração em segundos para o formato de exibição."""
    if not seconds:
        return "00:00"

    seconds = int(float(seconds))

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


def build_file_list(directory, url_prefix):

    """Monta os dados dos arquivos de uma pasta para exibição no painel."""
    files = []

    for file in sorted(
        directory.iterdir(),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    ):

        if not file.is_file():
            continue

        files.append({
            "name": file.name,
            "size": format_size(file.stat().st_size),
            "extension": file.suffix.upper(),
            "url": f"{url_prefix}/{quote(file.name)}"
        })

    return files


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    username: str = Depends(authenticate)
):
    """Exibe a página principal protegida do servidor de mídias."""
    return templates.TemplateResponse(
	request=request,
        name="index.html",
        context={}
        
    )


@app.get("/status")
def status():

    """Retorna o estado básico do serviço."""
    return {
        "status": "online",
        "service": "Holyrics Media Server"
    }

from fastapi import Query

@app.get("/webhook/whatsapp")
def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """Valida a solicitação inicial de verificação do webhook do WhatsApp."""
    VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)

    return {"error": "Token de verificação inválido"}

@app.post("/webhook/whatsapp")
async def receive_whatsapp_webhook(request: Request):

    """Processa mensagens e eventos recebidos do WhatsApp e encaminha cada fluxo."""
    try:
        data = await request.json()

        entry = data.get("entry", [])

        for entry_item in entry:

            changes = entry_item.get("changes", [])

            for change in changes:

                value = change.get("value", {})

                contacts = value.get("contacts", [])
                messages = value.get("messages", [])

                for message in messages:

                    message_id = message.get("id")
                    sender = message.get("from")
                    message_type = message.get("type")

                    if message_id:
                        if message_id in processed_whatsapp_message_ids:
                            processed_whatsapp_message_ids.move_to_end(message_id)
                            logging.info(
                                "WHATSAPP | Mensagem duplicada ignorada | ID: %s",
                                message_id,
                            )
                            continue

                        processed_whatsapp_message_ids[message_id] = None
                        if len(processed_whatsapp_message_ids) > WHATSAPP_MESSAGE_ID_CACHE_LIMIT:
                            processed_whatsapp_message_ids.popitem(last=False)

                    if not is_authorized_whatsapp_sender(sender):
                        if sender:
                            # Remove any session data if authorization was revoked.
                            whatsapp_menu_state.pop(sender, None)
                            eventos_pendentes.pop(sender, None)
                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "🔒 Acesso restrito. Este WhatsApp é destinado aos membros autorizados da igreja. Seu número não está cadastrado para utilizar os serviços.",
                                )
                            )
                        continue

                    print(
                        flush=True
                    )

                    sender_name = "Desconhecido"

                    if contacts:
                        sender_name = contacts[0].get(
                            "profile", {}
                        ).get(
                            "name",
                            "Desconhecido"
                        )

                    if message_type == "text":

                        text = message.get(
                            "text", {}
                        ).get(
                            "body",
                            ""
                        )

                        text = text.strip()


                        current_menu = whatsapp_menu_state.get(sender)

                        if current_menu == "buscando_musica_tema":

                            if text == "0":
                                whatsapp_menu_state.pop(sender, None)
                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "👋 Menu principal\n\n"
                                        "1️⃣ Horários\n"
                                        "2️⃣ Escalas\n"
                                        "3️⃣ Eventos\n"
                                        "4️⃣ Envio de Mídias\n"
                                        "5️⃣ Ofertas\n"
                                        "6️⃣ Buscar músicas por tema",
                                    )
                                )
                            elif len(text) > 250:
                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "Digite um tema curto, com até 250 caracteres, "
                                        "ou 0 para voltar ao menu."
                                    )
                                )
                            else:
                                try:
                                    ranked = await asyncio.to_thread(
                                        search_songs_by_theme,
                                        text,
                                    )
                                    whatsapp_song_theme_results[sender] = {
                                        "theme": text,
                                        "ranked": ranked,
                                        "offset": 0,
                                    }
                                    whatsapp_menu_state[sender] = (
                                        "resultado_busca_musica_tema"
                                    )
                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            format_song_theme_page(
                                                text,
                                                ranked,
                                                0,
                                            ),
                                        )
                                    )
                                except Exception:
                                    logging.exception(
                                        "WHATSAPP | Falha na busca temática de músicas"
                                    )
                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "⚠️ Não foi possível consultar as músicas agora.\n\n"
                                            "Tente novamente ou digite 0 para voltar ao menu."
                                        )
                                    )

                        elif current_menu == "resultado_busca_musica_tema":

                            search_data = whatsapp_song_theme_results.get(sender)
                            if not search_data:
                                whatsapp_menu_state[sender] = "buscando_musica_tema"
                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "Digite um tema para pesquisar nas músicas, "
                                        "ou 0 para voltar ao menu."
                                    )
                                )
                            elif text == "0":
                                whatsapp_song_theme_results.pop(sender, None)
                                whatsapp_menu_state.pop(sender, None)
                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "👋 Menu principal\n\n"
                                        "1️⃣ Horários\n"
                                        "2️⃣ Escalas\n"
                                        "3️⃣ Eventos\n"
                                        "4️⃣ Envio de Mídias\n"
                                        "5️⃣ Ofertas\n"
                                        "6️⃣ Buscar músicas por tema",
                                    )
                                )
                            elif text == "2":
                                whatsapp_song_theme_results.pop(sender, None)
                                whatsapp_menu_state[sender] = "buscando_musica_tema"
                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "🔎 Digite outro tema para pesquisar, "
                                        "ou 0 para voltar ao menu."
                                    )
                                )
                            elif text == "1":
                                next_offset = (
                                    search_data["offset"] + SONG_THEME_PAGE_SIZE
                                )
                                if next_offset < len(search_data["ranked"]):
                                    search_data["offset"] = next_offset
                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            format_song_theme_page(
                                                search_data["theme"],
                                                search_data["ranked"],
                                                next_offset,
                                            ),
                                        )
                                    )
                                else:
                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "Não há mais resultados para este tema.\n\n"
                                            "2️⃣ Nova consulta\n"
                                            "0️⃣ Menu principal"
                                        )
                                    )
                            else:
                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "Escolha 1 para ver mais, 2 para pesquisar outro tema, "
                                        "ou 0 para voltar ao menu."
                                    )
                                )

                        elif current_menu == "esperando_youtube":

                            youtube_url = text.strip()

                            if (
                                "youtube.com/" not in youtube_url
                                and "youtu.be/" not in youtube_url
                            ):

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "⚠️ O link enviado não parece ser um link válido do YouTube.\n\n"
                                        "Envie novamente o link do vídeo do YouTube."
                                    )
                                )

                                return

                            logging.info(
                                "WHATSAPP | Link YouTube recebido pelo menu | URL: %s",
                                youtube_url
                            )

                            print(
                                f"🎬 YOUTUBE PELO MENU\n"
                                f"🔗 URL: {youtube_url}",
                                flush=True
                            )

                            whatsapp_menu_state.pop(sender, None)

                           #asyncio.create_task(
                            #   download_youtube(youtube_url)
                           #)
                            asyncio.create_task(
                                 download_youtube(
                                     youtube_url,
                                     sender
                                 )
                            )

                            return

                        elif current_menu == "horarios":

                            if text.strip() == "0":

                                whatsapp_menu_state.pop(sender, None)

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "👋 Voltamos ao menu principal.\n\n"
                                        "Escolha uma opção:\n\n"
                                        "1️⃣ Horários\n"
                                        "2️⃣ Escalas\n"
                                        "3️⃣ Eventos\n"
                                        "4️⃣ Envio de Mídias\n"
                                        "5️⃣ Ofertas\n"
                                        "6️⃣ Buscar músicas por tema"
                                    )
                                )

                            else:

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ Opção inválida.\n\n"
                                        "Digite 0 para voltar ao menu principal."
                                    )
                                )

                        elif current_menu == "eventos_menu":

                            if text.strip() == "1":

                                import sys
                                sys.path.insert(
                                    0,
                                    "/opt/holyrics/escala"
                                )

                                from eventos import (
                                    consultar_proximos,
                                    formatar_eventos
                                )

                                resultado = consultar_proximos()

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        formatar_eventos(
                                            resultado,
                                            "📅 PRÓXIMOS EVENTOS"
                                        )
                                    )
                                )

                                whatsapp_menu_state[sender] = "eventos_pos_resultado"

                            elif text.strip() == "2":

                                whatsapp_menu_state[sender] = "eventos_data"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📅 CONSULTAR EVENTOS POR DATA\n\n"
                                        "Digite a data no formato:\n"
                                        "DD/MM/AAAA\n\n"
                                        "0️⃣ Voltar"
                                    )
                                )

                            elif text.strip() == "3":

                                whatsapp_menu_state[sender] = "eventos_mes"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📅 CONSULTAR EVENTOS POR MÊS\n\n"
                                        "Digite o mês no formato:\n"
                                        "MM/AAAA\n\n"
                                        "Exemplo: 10/2026\n\n"
                                        "0️⃣ Voltar"
                                    )
                                )

                            elif text.strip() == "4":

                                import sys
                                sys.path.insert(
                                    0,
                                    "/opt/holyrics/escala"
                                )

                                from eventos import (
                                    consultar_todos,
                                    formatar_eventos
                                )

                                resultado = consultar_todos()

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        formatar_eventos(
                                            resultado,
                                            "📅 TODOS OS EVENTOS"
                                        )
                                    )
                                )

                                whatsapp_menu_state[sender] = "eventos_pos_resultado"

                            elif text.strip() == "5":

                                whatsapp_menu_state[sender] = "esperando_convite_evento"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📅 *CADASTRAR EVENTO*\n\n"
                                        "Envie uma imagem do convite ou cartaz do evento.\n\n"
                                        "🤖 Vou identificar automaticamente:\n"
                                        "• Data\n"
                                        "• Nome do evento\n"
                                        "• Horário\n"
                                        "• Local\n"
                                        "• Outras informações\n\n"
                                        "Depois mostrarei os dados para sua confirmação.\n\n"
                                        "0️⃣ Cancelar"
                                    )
                                )

                            elif text.strip() == "0":

                                whatsapp_menu_state.pop(sender, None)

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "👋 Voltamos ao menu principal.\n\n"
                                        "Escolha uma opção:\n\n"
                                        "1️⃣ Horários\n"
                                        "2️⃣ Escalas\n"
                                        "3️⃣ Eventos\n"
                                        "4️⃣ Envio de Mídias\n"
                                        "5️⃣ Ofertas\n"
                                        "6️⃣ Buscar músicas por tema"
                                    )
                                )

                            else:

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ Opção inválida.\n\n"
                                        "Digite uma opção de 0 a 4."
                                    )
                                )


                        elif current_menu == "ofertas":

                            if text.strip() == "0":

                                whatsapp_menu_state.pop(sender, None)

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "👋 Voltamos ao menu principal.\n\n"
                                        "Escolha uma opção:\n\n"
                                        "1️⃣ Horários\n"
                                        "2️⃣ Escalas\n"
                                        "3️⃣ Eventos\n"
                                        "4️⃣ Envio de Mídias\n"
                                        "5️⃣ Ofertas\n"
                                        "6️⃣ Buscar músicas por tema"
                                    )
                                )

                            else:

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ Opção inválida.\n\n"
                                        "Digite 0 para voltar ao menu principal."
                                    )
                                )

                        elif current_menu == "escala_menu":

                            if text.strip() == "1":

                                try:
                                    import sys
                                    sys.path.insert(
                                        0,
                                        "/opt/holyrics/escala"
                                    )

                                    from escala import (
                                        formatar_escala_completa
                                    )

                                    mensagem = formatar_escala_completa()

                                    mensagem += (
                                        "\n\n"
                                        "🔄 *O que deseja fazer?*\n\n"
                                        "1️⃣ Nova consulta\n"
                                        "0️⃣ Finalizar"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "escala_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            mensagem
                                        )
                                    )

                                except Exception:

                                    logging.exception(
                                        "ESCALA | Erro na escala completa"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "escala_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Não foi possível consultar a escala no momento.\n\n"
                                            "🔄 *O que deseja fazer?*\n\n"
                                            "1️⃣ Nova consulta\n"
                                            "0️⃣ Finalizar"
                                        )
                                    )


                            elif text.strip() == "2":

                                whatsapp_menu_state[sender] = "escala_data"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📅 *CONSULTAR POR DATA*\n\n"
                                        "Digite a data desejada no formato:\n\n"
                                        "DD/MM/AAAA\n\n"
                                        "Exemplo: 20/09/2026\n\n"
                                        "0️⃣ Voltar"
                                    )
                                )


                            elif text.strip() == "3":

                                whatsapp_menu_state[sender] = "escala_nome"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "🔎 *CONSULTAR POR NOME*\n\n"
                                        "Digite o nome que deseja consultar.\n\n"
                                        "Você pode digitar apenas parte do nome.\n\n"
                                        "Exemplo: Luciano\n\n"
                                        "0️⃣ Voltar"
                                    )
                                )

                            elif text.strip() == "4":

                                whatsapp_menu_state[sender] = "escala_mes"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📅 *CONSULTAR POR MÊS*\n\n"
                                        "Escolha o mês:\n\n"
                                        "1️⃣ Julho\n"
                                        "2️⃣ Agosto\n"
                                        "3️⃣ Setembro\n"
                                        "4️⃣ Outubro\n\n"
                                        "0️⃣ Voltar"
                                    )
                                )

                            elif text.strip() == "5":

                                try:
                                    import sys
                                    sys.path.insert(
                                        0,
                                        "/opt/holyrics/escala"
                                    )

                                    from escala import (
                                        formatar_intercambios
                                    )

                                    mensagem = formatar_intercambios()

                                    mensagem += (
                                        "\n\n"
                                        "🔄 *O que deseja fazer?*\n\n"
                                        "1️⃣ Nova consulta\n"
                                        "0️⃣ Finalizar"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "escala_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            mensagem
                                        )
                                    )

                                except Exception:

                                    logging.exception(
                                        "ESCALA | Erro na consulta de intercâmbios"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "escala_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Não foi possível consultar os intercâmbios no momento.\n\n"
                                            "🔄 *O que deseja fazer?*\n\n"
                                            "1️⃣ Nova consulta\n"
                                            "0️⃣ Finalizar"
                                        )
                                    )




                            elif text.strip() == "0":

                                whatsapp_menu_state.pop(sender, None)

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "👋 Voltamos ao menu principal.\n\n"
                                        "Escolha uma opção:\n\n"
                                        "1️⃣ Horários\n"
                                        "2️⃣ Escalas\n"
                                        "3️⃣ Eventos\n"
                                        "4️⃣ Envio de Mídias\n"
                                        "5️⃣ Ofertas\n"
                                        "6️⃣ Buscar músicas por tema"
                                    )
                                )


                            else:

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ Opção inválida.\n\n"
                                        "Escolha uma opção de 1 a 5 ou 0 para voltar."
                                    )
                                )

                        elif current_menu == "editando_evento_descricao":

                            if text.strip() == "0":

                                whatsapp_menu_state[sender] = "revisando_evento"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "↩️ Alteração cancelada.\n\n"
                                        "Voltando aos dados do evento."
                                    )
                                )

                            elif not text.strip():

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ A descrição não pode ficar vazia.\n\n"
                                        "Digite as informações adicionais do evento.\n\n"
                                        "Exemplo: Pregadores: João e Maria.\n\n"
                                        "0️⃣ Cancelar"
                                    )
                                )

                            else:

                                dados = eventos_pendentes.get(sender)

                                if dados:

                                    dados["descricao"] = text.strip()

                                    whatsapp_menu_state[sender] = "revisando_evento"

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            montar_mensagem_revisao_evento(dados)
                                        )
                                    )

                                else:

                                    whatsapp_menu_state[sender] = "eventos_menu"

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Não há evento pendente para edição."
                                        )
                                    )


                        elif current_menu == "editando_evento_local":

                            if text.strip() == "0":

                                whatsapp_menu_state[sender] = "revisando_evento"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "↩️ Alteração cancelada.\n\n"
                                        "Voltando aos dados do evento."
                                    )
                                )

                            elif not text.strip():

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ O local não pode ficar vazio.\n\n"
                                        "Digite o local ou endereço do evento.\n\n"
                                        "0️⃣ Cancelar"
                                    )
                                )

                            else:

                                dados = eventos_pendentes.get(sender)

                                if dados:

                                    dados["local"] = text.strip()

                                    whatsapp_menu_state[sender] = "revisando_evento"

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            montar_mensagem_revisao_evento(dados)
                                        )
                                    )

                                else:

                                    whatsapp_menu_state[sender] = "eventos_menu"

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Não há evento pendente para edição."
                                        )
                                    )


                        elif current_menu == "editando_evento_horario":

                            if text.strip() == "0":

                                whatsapp_menu_state[sender] = "revisando_evento"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "↩️ Alteração cancelada.\n\n"
                                        "Voltando aos dados do evento."
                                    )
                                )

                            elif not text.strip():

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ O horário não pode ficar vazio.\n\n"
                                        "Digite o horário do evento.\n\n"
                                        "Exemplo: 19:30\n\n"
                                        "0️⃣ Cancelar"
                                    )
                                )

                            else:

                                dados = eventos_pendentes.get(sender)

                                if dados:

                                    dados["horario"] = text.strip()

                                    whatsapp_menu_state[sender] = "revisando_evento"

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            montar_mensagem_revisao_evento(dados)
                                        )
                                    )

                                else:

                                    whatsapp_menu_state[sender] = "eventos_menu"

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Não há evento pendente para edição."
                                        )
                                    )


                        elif current_menu == "editando_evento_nome":

                            if text.strip() == "0":

                                whatsapp_menu_state[sender] = "revisando_evento"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "↩️ Alteração cancelada.\n\n"
                                        "Voltando aos dados do evento."
                                    )
                                )

                            elif not text.strip():

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ O nome do evento não pode ficar vazio.\n\n"
                                        "Digite o novo nome do evento.\n\n"
                                        "0️⃣ Cancelar"
                                    )
                                )

                            else:

                                dados = eventos_pendentes.get(sender)

                                if dados:

                                    dados["evento"] = text.strip()

                                    whatsapp_menu_state[sender] = "revisando_evento"

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            montar_mensagem_revisao_evento(dados)
                                        )
                                    )

                                else:

                                    whatsapp_menu_state[sender] = "eventos_menu"

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Não há evento pendente para edição."
                                        )
                                    )


                        elif current_menu == "editando_evento_data":

                            if text.strip() == "0":

                                whatsapp_menu_state[sender] = "revisando_evento"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "↩️ Alteração cancelada.\n\n"
                                        "Voltando aos dados do evento."
                                    )
                                )

                            elif not text.strip():

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ A data não pode ficar vazia.\n\n"
                                        "Digite a nova data no formato "
                                        "DD/MM/AAAA.\n\n"
                                        "0️⃣ Cancelar"
                                    )
                                )

                            else:

                                data_digitada = text.strip()

                                if " a " in data_digitada:
                                    data_digitada = data_digitada.split(" a ", 1)[0].strip()

                                try:
                                    data_validada = datetime.strptime(
                                        data_digitada,
                                        "%d/%m/%Y"
                                    )

                                except ValueError:

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Data inválida.\n\n"
                                            "Digite uma data válida no formato "
                                            "DD/MM/AAAA.\n\n"
                                            "Exemplo: 17/10/2026\n\n"
                                            "0️⃣ Cancelar"
                                        )
                                    )

                                else:

                                    dados = eventos_pendentes.get(sender)

                                    if dados:

                                        dados["data"] = data_validada.strftime(
                                            "%d/%m/%Y"
                                        )

                                        whatsapp_menu_state[sender] = "revisando_evento"

                                        asyncio.create_task(
                                            send_whatsapp_message(
                                                sender,
                                                montar_mensagem_revisao_evento(dados)
                                            )
                                        )

                                    else:

                                        whatsapp_menu_state[sender] = "eventos_menu"

                                        asyncio.create_task(
                                            send_whatsapp_message(
                                                sender,
                                                "❌ Não há evento pendente para edição."
                                            )
                                        )


                        elif current_menu == "eventos_data":

                            if text.strip() == "0":

                                whatsapp_menu_state[sender] = "eventos_menu"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📅 *EVENTOS*\n\n"
                                        "Escolha uma opção:\n\n"
                                        "1️⃣ Próximos eventos\n"
                                        "2️⃣ Consultar por data\n"
                                        "3️⃣ Consultar por mês\n"
                                        "4️⃣ Ver todos os eventos\n"
                                        "5️⃣ Cadastrar novo evento\n\n"
                                        "0️⃣ Voltar"
                                    )
                                )

                            else:

                                try:
                                    import sys
                                    sys.path.insert(
                                        0,
                                        "/opt/holyrics/escala"
                                    )

                                    from eventos import (
                                        consultar_data,
                                        formatar_eventos
                                    )

                                    resultado = consultar_data(
                                        text.strip()
                                    )

                                    mensagem = formatar_eventos(
                                        resultado,
                                        "📅 EVENTOS"
                                    )

                                    mensagem += (
                                        "\n\n"
                                        "🔄 *O que deseja fazer?*\n\n"
                                        "1️⃣ Nova consulta\n"
                                        "0️⃣ Finalizar"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "eventos_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            mensagem
                                        )
                                    )

                                except Exception as e:

                                    print(
                                        f"Erro ao consultar eventos por data: {e}"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Não foi possível consultar "
                                            "os eventos.\n\n"
                                            "Tente novamente."
                                        )
                                    )

                        elif current_menu == "revisando_evento":

                            dados = eventos_pendentes.get(sender)

                            if not dados:
                                whatsapp_menu_state[sender] = "eventos_menu"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ Não há evento pendente para revisão."
                                    )
                                )

                            elif text.strip() == "0":

                                eventos_pendentes.pop(sender, None)
                                whatsapp_menu_state[sender] = "eventos_menu"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ Cadastro do evento cancelado."
                                    )
                                )

                            elif text.strip() in {"1", "2", "3", "4", "5"}:

                                campo_edicao = {
                                    "1": "editando_evento_data",
                                    "2": "editando_evento_nome",
                                    "3": "editando_evento_horario",
                                    "4": "editando_evento_local",
                                    "5": "editando_evento_descricao"
                                }

                                whatsapp_menu_state[sender] = campo_edicao[
                                    text.strip()
                                ]

                                mensagens_edicao = {
                                    "1": "📅 ALTERAR DATA\n\nDigite a nova data no formato DD/MM/AAAA.\n\nExemplo: 17/10/2026\n\n0️⃣ Cancelar",
                                    "2": "🎯 ALTERAR EVENTO\n\nDigite o novo nome do evento.\n\n0️⃣ Cancelar",
                                    "3": "🕐 ALTERAR HORÁRIO\n\nDigite o novo horário.\n\nExemplo: 19:30\n\n0️⃣ Cancelar",
                                    "4": "📍 ALTERAR LOCAL\n\nDigite o novo local ou endereço.\n\n0️⃣ Cancelar",
                                    "5": "📝 ALTERAR DESCRIÇÃO\n\nDigite a nova descrição ou outras informações do evento.\n\n0️⃣ Cancelar"
                                }

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        mensagens_edicao[text.strip()]
                                    )
                                )

                            elif text.strip() == "6":

                                try:

                                    import sys
                                    sys.path.insert(
                                        0,
                                        "/opt/holyrics/escala"
                                    )

                                    from eventos import cadastrar_evento

                                    data_cadastro = dados.get("data", "").strip()

                                    if " a " in data_cadastro:
                                        data_cadastro = data_cadastro.split(" a ", 1)[0].strip()

                                    resultado = cadastrar_evento(
                                        data_cadastro,
                                        dados.get("evento", ""),
                                        dados.get("horario", ""),
                                        dados.get("local", ""),
                                        dados.get("descricao", "")
                                    )

                                    eventos_pendentes.pop(sender, None)
                                    whatsapp_menu_state[sender] = "eventos_menu"

                                    mensagem_sucesso = (
                                        "✅ *EVENTO CADASTRADO COM SUCESSO!*\\n\\n"
                                        f"📅 {resultado['data'].strftime('%d/%m/%Y')}\\n"
                                        f"🎯 {resultado['evento']}\\n"
                                    )

                                    if resultado.get("horario"):
                                        mensagem_sucesso += (
                                            f"🕐 {resultado['horario'].strftime('%H:%M')}\\n"
                                        )

                                    if resultado.get("local"):
                                        mensagem_sucesso += (
                                            f"📍 {resultado['local']}\\n"
                                        )

                                    if resultado.get("descricao"):
                                        mensagem_sucesso += (
                                            f"📝 {resultado['descricao']}\\n"
                                        )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            mensagem_sucesso
                                        )
                                    )

                                except Exception as error:

                                    logging.exception(
                                        "WHATSAPP | Erro ao cadastrar evento: %s",
                                        error
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Não foi possível cadastrar o evento.\\n\\n"
                                            f"Motivo: {error}\\n\\n"
                                            "Os dados continuam pendentes para correção."
                                        )
                                    )

                            else:

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ Opção inválida.\n\n"
                                        "Escolha uma opção de 0 a 6."
                                    )
                                )


                        elif current_menu == "eventos_mes":

                            if text.strip() == "0":

                                whatsapp_menu_state[sender] = "eventos_menu"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📅 *EVENTOS*\n\n"
                                        "Escolha uma opção:\n\n"
                                        "1️⃣ Próximos eventos\n"
                                        "2️⃣ Consultar por data\n"
                                        "3️⃣ Consultar por mês\n"
                                        "4️⃣ Ver todos os eventos\n\n"
                                        "0️⃣ Voltar"
                                    )
                                )

                            else:

                                try:
                                    import sys
                                    sys.path.insert(
                                        0,
                                        "/opt/holyrics/escala"
                                    )

                                    from eventos import (
                                        consultar_mes,
                                        formatar_eventos
                                    )

                                    resultado = consultar_mes(
                                        text.strip()
                                    )

                                    mensagem = formatar_eventos(
                                        resultado,
                                        "📅 EVENTOS"
                                    )

                                    mensagem += (
                                        "\n\n"
                                        "🔄 *O que deseja fazer?*\n\n"
                                        "1️⃣ Nova consulta\n"
                                        "0️⃣ Finalizar"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "eventos_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            mensagem
                                        )
                                    )

                                except Exception as e:

                                    print(
                                        f"Erro ao consultar eventos por mês: {e}"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Não foi possível consultar "
                                            "os eventos.\n\n"
                                            "Tente novamente."
                                        )
                                    )





                        elif current_menu == "escala_data":

                            if text.strip() == "0":

                                whatsapp_menu_state[sender] = "escala_menu"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📅 *ESCALA DE REUNIÕES*\n\n"
                                        "Escolha uma opção:\n\n"
                                        "1️⃣ Ver escala completa\n"
                                        "2️⃣ Consultar por data\n"
                                        "3️⃣ Consultar por nome\n"
                                        "4️⃣ Consultar por mês\n"
                                        "5️⃣ Consultar Reuniões de Intercâmbio\n\n"
                                        "0️⃣ Voltar"
                                    )
                                )

                            else:

                                try:
                                    import sys
                                    sys.path.insert(
                                        0,
                                        "/opt/holyrics/escala"
                                    )

                                    from escala import (
                                        formatar_escala_data
                                    )

                                    mensagem = formatar_escala_data(
                                        text.strip()
                                    )

                                    mensagem += (
                                        "\n\n"
                                        "🔄 *O que deseja fazer?*\n\n"
                                        "1️⃣ Nova consulta\n"
                                        "0️⃣ Finalizar"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "escala_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            mensagem
                                        )
                                    )

                                except Exception:

                                    logging.exception(
                                        "ESCALA | Erro na consulta por data"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "escala_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Não foi possível consultar a escala no momento.\n\n"
                                            "🔄 *O que deseja fazer?*\n\n"
                                            "1️⃣ Nova consulta\n"
                                            "0️⃣ Finalizar"
                                        )
                                    )


                        elif current_menu == "escala_nome":

                            if text.strip() == "0":

                                whatsapp_menu_state[sender] = "escala_menu"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📅 *ESCALA DE REUNIÕES*\n\n"
                                        "Escolha uma opção:\n\n"
                                        "1️⃣ Ver escala completa\n"
                                        "2️⃣ Consultar por data\n"
                                        "3️⃣ Consultar por nome\n"
                                        "4️⃣ Consultar por mês\n"
                                        "5️⃣ Consultar Reniões de Intercâmbio\n\n"
                                        "0️⃣ Voltar"
                                    )
                                )

                            else:

                                try:
                                    import sys
                                    sys.path.insert(
                                        0,
                                        "/opt/holyrics/escala"
                                    )

                                    from escala import (
                                        formatar_escala_nome
                                    )

                                    mensagem = formatar_escala_nome(
                                        text.strip()
                                    )

                                    mensagem += (
                                        "\n\n"
                                        "🔄 *O que deseja fazer?*\n\n"
                                        "1️⃣ Nova consulta\n"
                                        "0️⃣ Finalizar"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "escala_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            mensagem
                                        )
                                    )

                                except Exception:

                                    logging.exception(
                                        "ESCALA | Erro na consulta por nome"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "escala_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Não foi possível consultar a escala no momento.\n\n"
                                            "🔄 *O que deseja fazer?*\n\n"
                                            "1️⃣ Nova consulta\n"
                                            "0️⃣ Finalizar"
                                        )
                                    )


                        elif current_menu == "escala_mes":

                            if text.strip() == "0":

                                whatsapp_menu_state[sender] = "escala_menu"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📅 *ESCALA DE REUNIÕES*\n\n"
                                        "Escolha uma opção:\n\n"
                                        "1️⃣ Ver escala completa\n"
                                        "2️⃣ Consultar por data\n"
                                        "3️⃣ Consultar por nome\n"
                                        "4️⃣ Consultar por mês\n"
                                        "5️⃣ Consultar Reuniões de Intercâmbio\n\n"
                                        "0️⃣ Voltar"
                                    )
                                )

                            else:

                                try:
                                    import sys
                                    sys.path.insert(
                                        0,
                                        "/opt/holyrics/escala"
                                    )

                                    from escala import (
                                        formatar_escala_mes
                                    )

                                    meses = {
                                        "1": "07/2026",
                                        "2": "08/2026",
                                        "3": "09/2026",
                                        "4": "10/2026",
                                    }

                                    mes_escolhido = meses.get(
                                        text.strip()
                                    )

                                    if not mes_escolhido:
                                        mensagem = (
                                            "❌ Opção inválida.\n\n"
                                            "Escolha uma opção de 1 a 4 "
                                            "ou 0 para voltar."
                                        )

                                        asyncio.create_task(
                                            send_whatsapp_message(
                                                sender,
                                                mensagem
                                            )
                                        )

                                    else:
                                        mensagem = formatar_escala_mes(
                                            mes_escolhido
                                        )

                                    mensagem += (
                                        "\n\n"
                                        "🔄 *O que deseja fazer?*\n\n"
                                        "1️⃣ Nova consulta\n"
                                        "0️⃣ Finalizar"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "escala_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            mensagem
                                        )
                                    )

                                except Exception:

                                    logging.exception(
                                        "ESCALA | Erro na consulta por mês"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "escala_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Não foi possível consultar a escala no momento.\n\n"
                                            "🔄 *O que deseja fazer?*\n\n"
                                            "1️⃣ Nova consulta\n"
                                            "0️⃣ Finalizar"
                                        )
                                    )


                        elif current_menu == "escala_intercambio":

                            if text.strip() == "0":

                                whatsapp_menu_state[sender] = "escala_menu"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📅 *ESCALA DE REUNIÕES*\n\n"
                                        "Escolha uma opção:\n\n"
                                        "1️⃣ Ver escala completa\n"
                                        "2️⃣ Consultar por data\n"
                                        "3️⃣ Consultar por nome\n"
                                        "4️⃣ Consultar por mês\n"
                                        "5️⃣ Consultar Reuniões de Intercâmbio\n\n"
                                        "0️⃣ Voltar"
                                    )
                                )

                            else:

                                try:
                                    import sys
                                    sys.path.insert(
                                        0,
                                        "/opt/holyrics/escala"
                                    )

                                    from escala import (
                                        formatar_intercambio
                                    )

                                    mensagem = formatar_intercambio(
                                        text.strip()
                                    )

                                    mensagem += (
                                        "\n\n"
                                        "🔄 *O que deseja fazer?*\n\n"
                                        "1️⃣ Nova consulta\n"
                                        "0️⃣ Finalizar"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "escala_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            mensagem
                                        )
                                    )

                                except Exception:

                                    logging.exception(
                                        "ESCALA | Erro na consulta de intercâmbio"
                                    )

                                    whatsapp_menu_state[sender] = (
                                        "escala_pos_resultado"
                                    )

                                    asyncio.create_task(
                                        send_whatsapp_message(
                                            sender,
                                            "❌ Não foi possível consultar o intercâmbio no momento.\n\n"
                                            "🔄 *O que deseja fazer?*\n\n"
                                            "1️⃣ Nova consulta\n"
                                            "0️⃣ Finalizar"
                                        )
                                    )

                        elif current_menu == "eventos_pos_resultado":

                            if text.strip() == "1":

                                whatsapp_menu_state[sender] = "eventos_menu"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📅 *EVENTOS*\n\n"
                                        "Escolha uma opção:\n\n"
                                        "1️⃣ Próximos eventos\n"
                                        "2️⃣ Consultar por data\n"
                                        "3️⃣ Consultar por mês\n"
                                        "4️⃣ Ver todos os eventos\n\n"
                                        "0️⃣ Voltar"
                                    )
                                )

                            elif text.strip() == "0":

                                whatsapp_menu_state.pop(sender, None)

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "👋 Atendimento finalizado.\n\n"
                                        "Para acessar novamente o menu, "
                                        "envie uma nova mensagem."
                                    )
                                )

                            else:

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ Opção inválida.\n\n"
                                        "Digite 1 para nova consulta "
                                        "ou 0 para finalizar."
                                    )
                                )



                        elif current_menu == "escala_pos_resultado":

                            if text.strip() == "1":

                                whatsapp_menu_state[sender] = "escala_menu"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📅 *ESCALA DE REUNIÕES*\n\n"
                                        "Escolha uma opção:\n\n"
                                        "1️⃣ Ver escala completa\n"
                                        "2️⃣ Consultar por data\n"
                                        "3️⃣ Consultar por nome\n"
                                        "4️⃣ Consultar por mês\n"
                                        "5️⃣ Consultar Reuniões de Intercâmbio\n\n"
                                        "0️⃣ Voltar"
                                    )
                                )

                            elif text.strip() == "0":

                                whatsapp_menu_state.pop(sender, None)

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "👋 Consulta finalizada.\n\n"
                                        "Quando quiser, envie uma mensagem para acessar o menu novamente."
                                    )
                                )

                            else:

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ Opção inválida.\n\n"
                                        "Escolha:\n\n"
                                        "1️⃣ Nova consulta\n"
                                        "0️⃣ Finalizar"
                                    )
                                )


                        elif current_menu == "midias":



                            if text.strip() == "1":
                                whatsapp_menu_state[sender] = "esperando_video"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "🎥 Você escolheu Vídeo.\n\n"
                                        "Envie o vídeo que deseja adicionar ao Holyrics."
                                    )
                                )


                            elif text.strip() == "2":
                                whatsapp_menu_state[sender] = "esperando_imagem"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "🖼️ Você escolheu Imagem.\n\n"
                                        "Envie a imagem que deseja adicionar ao Holyrics."
                                    )
                                )


                            elif text.strip() == "3":
                                whatsapp_menu_state[sender] = "esperando_documento"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "📄 Você escolheu Documento.\n\n"
                                        "Envie o documento que deseja adicionar ao Holyrics."
                                    )
                                )

                            elif text.strip() == "4":

                                whatsapp_menu_state[sender] = "esperando_audio"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "🎵 Você escolheu Áudio.\n\n"
                                        "Envie o áudio que deseja adicionar ao Holyrics."
                                    )
                                )


                            elif text.strip() == "5":

                                whatsapp_menu_state[sender] = "esperando_youtube"

                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "▶️ Você escolheu YouTube.\n\n"
                                        "Envie o link do vídeo do YouTube."
                                    )
                                )

                            else:
                                asyncio.create_task(
                                    send_whatsapp_message(
                                        sender,
                                        "❌ Opção inválida.\n\n"
                                        "Escolha uma opção de 1 a 5."
                                    )
                                )

                        elif text.strip() == "1":

                            whatsapp_menu_state[sender] = "horarios"

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "🕐 *HORÁRIOS DAS REUNIÕES*\n\n"
                                    "📅 *DOMINGO*\n"
                                    "08:30 — Ceia do Senhor\n"
                                    "09:45 — Escola Bíblica Dominical\n"
                                    "19:30 — Pregação do Evangelho\n\n"
                                    "📅 *SÁBADO*\n"
                                    "20:00 — Culto de Jovens\n\n"
                                    "📅 *QUARTA-FEIRA*\n"
                                    "20:00 — Oração e Estudo\n\n"
                                    "0️⃣ Voltar ao menu principal"
                                )
                            )


                        elif text.strip() == "2":

                            whatsapp_menu_state[sender] = "escala_menu"

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "📅 *ESCALA DE REUNIÕES*\n\n"
                                    "Escolha uma opção:\n\n"
                                    "1️⃣ Ver escala completa\n"
                                    "2️⃣ Consultar por data\n"
                                    "3️⃣ Consultar por nome\n"
                                    "4️⃣ Consultar por mês\n"
                                    "5️⃣ Consultar Reuniões de Intercâmbio\n\n"
                                    "0️⃣ Voltar"
                                )
                            )

                        elif text.strip() == "3":

                            whatsapp_menu_state[sender] = "eventos_menu"

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "📅 *EVENTOS*\n\n"
                                    "Escolha uma opção:\n\n"
                                    "1️⃣ Próximos eventos\n"
                                    "2️⃣ Consultar por data\n"
                                    "3️⃣ Consultar por mês\n"
                                    "4️⃣ Ver todos os eventos\n"
                                    "5️⃣ Cadastrar novo evento\n\n"
                                    "0️⃣ Voltar"
                                )
                            )


                        elif text.strip() == "4":

                            whatsapp_menu_state[sender] = "midias"

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "🎬 ENVIO DE MÍDIAS\n\n"
                                    "Escolha o tipo de mídia:\n\n"
                                    "1️⃣ Vídeo\n"
                                    "2️⃣ Imagem\n"
                                    "3️⃣ Documento\n"
                                    "4️⃣ Áudio\n"
                                    "5️⃣ YouTube"
                                )
                            )

                        elif text.strip() == "5":

                            whatsapp_menu_state[sender] = "ofertas"

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "💰 *OFERTAS*\n\n"
                                    "Para realizar sua oferta, utilize a chave Pix\n"
                                    "da Casa de Oração Portinari.\n\n"
                                    "🔑 *Chave Pix:*"
                                )
                            )

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "25.358.639/0001-74"
                                )
                            )

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "\nQue Deus abençoe sua vida e sua contribuição! 🙏\n\n"
                                    "0️⃣ Voltar ao menu principal"
                                )
                            )

                        elif text.strip() == "6":

                            whatsapp_menu_state[sender] = "buscando_musica_tema"

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "🎵 *BUSCA DE MÚSICAS POR TEMA*\n\n"
                                    "Digite um tema, por exemplo: *a misericórdia de Deus*.\n\n"
                                    "0️⃣ Voltar ao menu principal"
                                )
                            )


                        else:

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "👋 Olá! Seja bem-vindo ao WhatsApp da Casa de Oração Portinari!\n\n"
                                    "Escolha uma opção:\n\n"
                                    "1️⃣ Horários\n"
                                    "2️⃣ Escalas\n"
                                    "3️⃣ Eventos\n"
                                    "4️⃣ Envio de Mídias\n"
                                    "5️⃣ Ofertas\n"
                                    "6️⃣ Buscar músicas por tema\n\n"
                                    "Digite o número da opção desejada."
                                )
                            )

                        if text.lower().startswith("youtube "):

                            youtube_url = text[8:].strip()

                            logging.info(
                                "WHATSAPP | Comando YouTube detectado | URL: %s",
                                youtube_url
                            )

                            print(
                                f"🎬 COMANDO YOUTUBE DETECTADO\n"
                                f"🔗 URL: {youtube_url}",
                                flush=True
                            )

                            asyncio.create_task(
                                download_youtube(youtube_url)
                            )

                        logging.info(
                            "WHATSAPP | Nome: %s | "
                            "Remetente: %s | "
                            "Mensagem: %s | ID: %s",
                            sender_name,
                            sender,
                            text,
                            message_id
                        )

                        print(
                            f"📱 WHATSAPP\n"
                            f"👤 Nome: {sender_name}\n"
                            f"📞 Remetente: {sender}\n"
                            f"💬 Mensagem: {text}\n"
                            f"🆔 ID: {message_id}",
                            flush=True
                        )


                    elif message_type == "document":

                        document = message.get("document", {})

                        if whatsapp_menu_state.get(sender) != "esperando_documento":

                            logging.info(
                                "WHATSAPP | Documento recebido fora do fluxo de envio. Ignorando."
                            )

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "⚠️ Para enviar um documento ao Holyrics, primeiro escolha:\n\n"
                                    "4️⃣ Envio de Mídias\n"
                                    "3️⃣ Documento\n\n"
                                    "Depois envie o documento novamente."
                                )
                            )

                            whatsapp_menu_state.pop(sender, None)

                            return

                        media_id = document.get("id")
                        original_filename = document.get(
                            "filename",
                            "documento"
                        )

                        filename = create_media_filename(
                            sender_name,
                            original_filename
                        )

                        mime_type = document.get("mime_type", "")

                        print(
                            f"📄 DOCUMENTO WHATSAPP\n"
                            f"📄 Arquivo: {filename}\n"
                            f"📦 MIME: {mime_type}",
                            flush=True
                        )

                        logging.info(
                            "WHATSAPP | Documento recebido | Arquivo: %s | MIME: %s",
                            filename,
                            mime_type
                        )

                        if media_id:

                            asyncio.create_task(
                                download_whatsapp_media(
                                    media_id,
                                    filename,
                                    sender,
                                    "document"
                                )
                            )

                            whatsapp_menu_state.pop(sender, None)

                        else:

                            logging.error(
                                "WHATSAPP | Documento sem media_id."
                            )

                    elif message_type == "image":

                        image = message.get("image", {})

                        estado_imagem = whatsapp_menu_state.get(sender)

                        # =====================================================
                        # FLUXO DE CADASTRO DE EVENTO
                        # =====================================================

                        if estado_imagem == "esperando_convite_evento":

                            media_id = image.get("id")
                            mime_type = image.get("mime_type", "")

                            extension = (
                                mime_type.split("/")[-1]
                                if "/" in mime_type
                                else "jpg"
                            )

                            original_filename = (
                                f"convite_{media_id}.{extension}"
                            )

                            filename = create_media_filename(
                                sender_name,
                                original_filename
                            )

                            print(
                                f"📅 CONVITE DE EVENTO WHATSAPP\n"
                                f"📄 Arquivo: {filename}\n"
                                f"📦 MIME: {mime_type}",
                                flush=True
                            )

                            logging.info(
                                "WHATSAPP | Convite de evento recebido | "
                                "Arquivo: %s | MIME: %s",
                                filename,
                                mime_type
                            )

                            if media_id:

                                try:

                                    caminho_imagem = await download_whatsapp_event_image(
                                        media_id,
                                        filename
                                    )

                                    print(
                                        "🤖 GEMINI | Iniciando interpretação do convite...",
                                        flush=True
                                    )

                                    dados_evento = await interpretar_convite_evento(
                                        caminho_imagem
                                    )

                                    print(
                                        "🤖 GEMINI | Dados identificados:",
                                        flush=True
                                    )

                                    print(
                                        json.dumps(
                                            dados_evento,
                                            ensure_ascii=False,
                                            indent=2
                                        ),
                                        flush=True
                                    )

                                    # Guarda os dados temporariamente para confirmação.
                                    eventos_pendentes[sender] = dados_evento

                                    whatsapp_menu_state[sender] = "revisando_evento"

                                    mensagem = (
                                        "📅 *DADOS DO EVENTO*\n\n"
                                        f"1️⃣ *Data:* {dados_evento.get('data') or 'Não informado'}\n"
                                        f"2️⃣ *Evento:* {dados_evento.get('evento') or 'Não informado'}\n"
                                        f"3️⃣ *Horário:* {dados_evento.get('horario') or 'Não informado'}\n"
                                        f"4️⃣ *Local:* {dados_evento.get('local') or 'Não informado'}\n"
                                        f"5️⃣ *Descrição:* {dados_evento.get('descricao') or 'Não informado'}\n\n"
                                        "Escolha o número do campo que deseja alterar.\n\n"
                                        "6️⃣ Confirmar cadastro\n"
                                        "0️⃣ Cancelar"
                                    )

                                    await send_whatsapp_message(sender, mensagem)

                                except Exception as error:

                                    logging.exception(
                                        "WHATSAPP | Erro ao processar convite de evento: %s",
                                        error
                                    )

                            else:

                                logging.error(
                                    "WHATSAPP | Convite de evento sem media_id."
                                )

                            return


                        # =====================================================
                        # FLUXO NORMAL DE IMAGEM PARA O HOLYRICS
                        # =====================================================

                        if estado_imagem != "esperando_imagem":

                            logging.info(
                                "WHATSAPP | Imagem recebida fora do fluxo de envio. Ignorando."
                            )

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "⚠️ Para enviar uma imagem ao Holyrics, primeiro escolha:\n\n"
                                    "4️⃣ Envio de Mídias\n"
                                    "2️⃣ Imagem\n\n"
                                    "Depois envie a imagem novamente."
                                )
                            )

                            whatsapp_menu_state.pop(sender, None)

                            return

                        media_id = image.get("id")
                        mime_type = image.get("mime_type", "")

                        # O WhatsApp normalmente não envia nome de arquivo para imagens.
                        extension = (
                            mime_type.split("/")[-1]
                            if "/" in mime_type
                            else "jpg"
                        )

                        original_filename = (
                            f"whatsapp_{media_id}.{extension}"
                        )

                        filename = create_media_filename(
                            sender_name,
                            original_filename
                        )

                        print(
                            f"🖼️ IMAGEM WHATSAPP\n"
                            f"📄 Arquivo: {filename}\n"
                            f"📦 MIME: {mime_type}",
                            flush=True
                        )

                        logging.info(
                            "WHATSAPP | Imagem recebida | "
                            "Arquivo: %s | MIME: %s",
                            filename,
                            mime_type
                        )

                        if media_id:

                            asyncio.create_task(
                                download_whatsapp_media(
                                    media_id,
                                    filename,
                                    sender,
                                    "image"
                                )
                            )

                        else:

                            logging.error(
                                "WHATSAPP | Imagem sem media_id."
                            )


                    elif message_type == "video":

                        video = message.get("video", {})


                        logging.info(
                            sender,
                            whatsapp_menu_state.get(sender)
                        )


                        if whatsapp_menu_state.get(sender) != "esperando_video":
                            logging.info(
                                "WHATSAPP | Vídeo recebido fora do fluxo de envio. Ignorando."
                            )

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "⚠️ Para enviar um vídeo ao Holyrics, primeiro escolha:\n\n"
                                    "4️⃣ Envio de Mídias\n"
                                    "1️⃣ Vídeo\n\n"
                                    "Depois envie o vídeo novamente."
                                )
                            )

                            whatsapp_menu_state.pop(sender, None)

                            return


                        media_id = video.get("id")
                        mime_type = video.get("mime_type", "video/mp4")

                        filename = create_media_filename(
                            sender_name,
                            f"whatsapp_{media_id}.mp4"
                        )

                        print(
                            f"🎬 VIDEO WHATSAPP\n"
                            f"📄 Arquivo: {filename}\n"
                            f"📦 MIME: {mime_type}",
                            flush=True
                        )

                        logging.info(
                            "WHATSAPP | Vídeo recebido | Arquivo: %s | MIME: %s",
                            filename,
                            mime_type
                        )

                        if media_id:

                            asyncio.create_task(
                                download_whatsapp_media(
                                     media_id,
                                     filename,
                                     sender,
                                     "video"
                               )
                            )

                        else:

                            logging.error(
                                "WHATSAPP | Vídeo sem media_id."
                            )

                    elif message_type == "audio":

                        audio = message.get("audio", {})

                        logging.info(
                            sender,
                            whatsapp_menu_state.get(sender)
                        )

                        if whatsapp_menu_state.get(sender) != "esperando_audio":

                            logging.info(
                                "WHATSAPP | Áudio recebido fora do fluxo de envio. Ignorando."
                            )

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "⚠️ Para enviar um áudio ao Holyrics, primeiro escolha:\n\n"
                                    "4️⃣ Envio de Mídias\n"
                                    "4️⃣ Áudio\n\n"
                                    "Depois envie o áudio novamente."
                                )
                            )

                            whatsapp_menu_state.pop(sender, None)

                            return

                        media_id = audio.get("id")
                        mime_type = audio.get("mime_type", "audio/mpeg")

                        extension = "mp3"

                        original_filename = f"whatsapp_{media_id}.{extension}"

                        filename = create_media_filename(
                            sender_name,
                            original_filename
                        )

                        print(
                            f"🎵 AUDIO WHATSAPP\n"
                            f"📄 Arquivo: {filename}\n"
                            f"📦 MIME: {mime_type}",
                            flush=True
                        )

                        logging.info(
                            "WHATSAPP | Áudio recebido | Arquivo: %s | MIME: %s",
                            filename,
                            mime_type
                        )

                        if media_id:

                            asyncio.create_task(
                                download_whatsapp_media(
                                    media_id,
                                    filename,
                                    sender,
                                    "audio"
                                )
                            )

                        else:

                           logging.error(
                               "WHATSAPP | Áudio sem media_id."
                           )

                    else:

                        logging.info(
                            "WHATSAPP | Tipo de mensagem: %s | "
                            "Remetente: %s | ID: %s",
                            message_type,
                            sender,
                            message_id
                        )

                        print(
                            f"📱 WHATSAPP\n"
                            f"👤 Nome: {sender_name}\n"
                            f"📞 Remetente: {sender}\n"
                            f"📦 Tipo: {message_type}\n"
                            f"🆔 ID: {message_id}",
                            flush=True
                        )

        return {"status": "received"}

    except Exception as error:

        logging.error(
            "Erro ao processar webhook WhatsApp: %s",
            error
        )

        print(
            f"❌ ERRO WEBHOOK WHATSAPP: {error}",
            flush=True
        )

        return {"status": "error"}

@app.post("/upload", response_class=HTMLResponse)
async def upload(
    file: UploadFile = File(...),
    username: str = Depends(authenticate)
):
    """Recebe arquivos enviados pelo painel web e os encaminha ao fluxo de mídia."""
    filename = Path(file.filename).name

    destination = INCOMING / filename

    with destination.open("wb") as buffer:
        shutil.copyfileobj(
            file.file,
            buffer
        )

    target_directory = classify_file(filename)

    if target_directory is None:

        error_destination = ERROR / filename

        shutil.move(
            str(destination),
            str(error_destination)
        )

        message = (
            "❌ Tipo de arquivo não permitido.<br>"
            f"Arquivo movido para: "
            f"{html.escape(str(error_destination))}"
        )

    else:

        media_names = {
            IMAGES: "🖼️ Imagem",
            VIDEOS: "🎬 Vídeo",
            PRESENTATIONS: "📄 Apresentação",
            AUDIO: "🔊 Áudio"
        }

        media_type = media_names.get(
            target_directory,
            target_directory.name
        )

        message = (
            "✅ Arquivo recebido com sucesso!"
        )

    return f"""
    <!DOCTYPE html>

    <html lang="pt-BR">

    <head>

        <meta charset="UTF-8">

        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <title>Holyrics Media Server</title>

        <style>

            body {{
                font-family: Arial, sans-serif;
                max-width: 700px;
                margin: 40px auto;
                padding: 20px;
            }}

            .result {{
                border: 1px solid #ccc;
                border-radius: 10px;
                padding: 30px;
            }}

            .success {{
                font-size: 24px;
                margin-bottom: 25px;
            }}

            .info {{
                font-size: 17px;
                line-height: 1.8;
            }}

            .back {{
                display: inline-block;
                margin-top: 25px;
                padding: 10px 20px;
                border: 1px solid #ccc;
                border-radius: 8px;
                text-decoration: none;
                color: inherit;
            }}

            .back:hover {{
                background: #f5f5f5;
            }}

        </style>

    </head>

    <body>

        <div class="result">

            <div class="success">
                {message}
            </div>

            <div class="info">

                📄 Arquivo:
                <strong>{html.escape(filename)}</strong>

                <br>

                📁 Tipo:
                <strong>{media_type}</strong>

                <br>

                ⏳ Aguardando envio para o computador do Holyrics.

            </div>

            <a class="back" href="/">
                ← Enviar outra mídia
            </a>

        </div>

    </body>

    </html>
    """

@app.get("/youtube/progress")
async def youtube_progress_status(
    username: str = Depends(authenticate)
):
    """Retorna o progresso atual do download do YouTube."""
    return youtube_progress

@app.post("/youtube", response_class=HTMLResponse)
async def youtube_download(
    url: str = Form(...),
    username: str = Depends(authenticate)
):
    """Inicia o download de um vídeo do YouTube solicitado pelo painel."""
    try:

        command = [
            "yt-dlp",

            "--no-playlist",

            "--print-json",

            "--newline",

            "--progress",

            "-f",
            "bv*[vcodec^=avc1][height<=720]+ba[acodec^=mp4a]/b[ext=mp4]",

            "--merge-output-format",
            "mp4",

            "-o",
	    "/data/incoming/%(title)s.%(ext)s",

            url
        ]

        youtube_progress["status"] = "downloading"
        youtube_progress["percent"] = 0
        youtube_progress["downloaded"] = ""
        youtube_progress["total"] = ""
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        while True:
            line = await asyncio.to_thread(
               process.stdout.readline
            )

            if not line:
                break

            line = line.strip()

            if "[download]" in line and "%" in line:
                try:
                    percent_text = line.split("%")[0].split()[-1]
                    percent = float(percent_text)

                    youtube_progress["status"] = "downloading"

                    if percent > youtube_progress["percent"]:
                        youtube_progress["percent"] = percent 

                    print(
                        f"Progresso YouTube: {percent:.1f}%",
                        flush=True
                    )

                except (ValueError, IndexError):
                    pass

        await asyncio.to_thread(process.wait)

        stdout = ""
        stderr = ""

        result = subprocess.CompletedProcess(
            command,
            process.returncode,
            stdout,
            stderr
        )


        if result.returncode != 0:

            error = html.escape(result.stderr[-3000:])
            
            youtube_progress["status"] = "error"

            return f"""
            <!DOCTYPE html>

            <html>

            <head>
                <meta charset="UTF-8">
                <title>Erro</title>
            </head>

            <body>

                <h1>❌ Erro ao baixar o vídeo</h1>

                <pre>{error}</pre>

                <br>

                <a href="/">
                    ← Voltar
                </a>

            </body>

            </html>
            """
        youtube_progress["status"] = "completed"
        youtube_progress["percent"] = 100

        video_info = None

        for line in result.stdout.splitlines():

            try:

                data = json.loads(line)

                if isinstance(data, dict) and "title" in data:

                    video_info = data

            except json.JSONDecodeError:

                continue

        title = (
            video_info.get("title", "Vídeo do YouTube")
            if video_info
            else "Vídeo do YouTube"
        )

        duration = (
            video_info.get("duration", 0)
            if video_info
            else 0
        )

        mp4_files = list(INCOMING.glob("*.mp4"))

        if not mp4_files:

            raise Exception(
                "Download concluído, mas o arquivo MP4 "
                "não foi encontrado."
            )

        video_file = max(
            mp4_files,
            key=lambda p: p.stat().st_mtime
        )

        file_size = video_file.stat().st_size

        safe_title = html.escape(title)

        return f"""
        <!DOCTYPE html>

        <html>

        <head>

            <meta charset="UTF-8">

            <title>Download concluído</title>

        </head>

        <body>

            <h1>✅ Download concluído!</h1>

            <h2>🎬 {safe_title}</h2>

            <p>
                📦 Tamanho:
                {format_size(file_size)}
            </p>

            <p>
                ⏱️ Duração:
                {format_duration(duration)}
            </p>

            <p>
                📁 Categoria: YouTube
            </p>

            <p>
                📍 {html.escape(str(video_file))}
            </p>

            <br>

            <a href="/youtube/list">
                📺 Ver vídeos baixados
            </a>

            <br><br>

            <a href="/">
                ← Voltar
            </a>

        </body>

        </html>
        """

    except subprocess.TimeoutExpired:

        message = "❌ O download excedeu o limite de 1 hora."

        return f"""
        <h1>{message}</h1>
        <a href="/">← Voltar</a>
        """

    except Exception as e:

        message = (
            "❌ Erro inesperado:<br><br>"
            f"<pre>{html.escape(str(e))}</pre>"
        )

        return f"""
        <h1>{message}</h1>
        <br>
        <a href="/">← Voltar</a>
        """


@app.get("/media/images", response_class=HTMLResponse)
def list_images(
    request: Request,
    username: str = Depends(authenticate)
):
    """Lista as imagens disponíveis para o painel."""
    files = build_file_list(
        IMAGES,
        "/media/file/images"
    )

    return templates.TemplateResponse(
	 request=request,
        name="media_list.html",
        context={
            "title": "Imagens",
            "icon": "🖼️",
            "media_type": "image",
            "files": files
        }
    )


@app.get("/media/videos", response_class=HTMLResponse)
def list_videos(
    request: Request,
    username: str = Depends(authenticate)
):
    """Lista os vídeos disponíveis para o painel."""
    files = build_file_list(
        VIDEOS,
        "/media/file/videos"
    )

    return templates.TemplateResponse(
	request=request,
        name="media_list.html",
        context={
            "title": "Vídeos",
            "icon": "🎬",
            "media_type": "video",
            "files": files
        }
    )


@app.get("/media/presentations", response_class=HTMLResponse)
def list_presentations(
    request: Request,
    username: str = Depends(authenticate)
):
    """Lista as apresentações disponíveis para o painel."""
    files = build_file_list(
        PRESENTATIONS,
        "/media/file/presentations"
    )

    return templates.TemplateResponse(
	request=request,
        name="presentation_list.html",
        context={
            "files": files
        }
    )


@app.get("/media/file/{category}/{filename:path}")
def media_file(
    category: str,
    filename: str,
    username: str = Depends(authenticate)
):
    """Entrega ao navegador um arquivo de mídia autorizado."""
    directories = {
        "images": IMAGES,
        "videos": VIDEOS,
        "presentations": PRESENTATIONS
    }

    directory = directories.get(category)

    if directory is None:

        return HTMLResponse(
            "Categoria inválida.",
            status_code=404
        )

    file_path = directory / Path(filename).name

    if not file_path.exists():

        return HTMLResponse(
            "Arquivo não encontrado.",
            status_code=404
        )

    return FileResponse(
        path=file_path,
        filename=file_path.name
    )


@app.get("/youtube/file/{filename:path}")
def youtube_file(
    filename: str,
    username: str = Depends(authenticate)
):
    """Entrega ao navegador um arquivo baixado do YouTube."""
    file_path = YOUTUBE / Path(filename).name

    if not file_path.exists():

        return HTMLResponse(
            content="Arquivo não encontrado.",
            status_code=404
        )

    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        filename=file_path.name
    )


@app.get("/youtube/list", response_class=HTMLResponse)
def youtube_list(
    request: Request,
    username: str = Depends(authenticate)
):
    """Lista os arquivos de vídeo do YouTube disponíveis no servidor."""
    files = build_file_list(
        YOUTUBE,
        "/youtube/file"
    )

    return templates.TemplateResponse(
	request=request,
        name="media_list.html",
        context={
            "title": "Vídeos do YouTube",
            "icon": "▶️",
            "media_type": "video",
            "files": files
        }
    )

