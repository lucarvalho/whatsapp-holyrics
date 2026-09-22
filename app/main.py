from fastapi import FastAPI, UploadFile, File, Form, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pathlib import Path
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
from datetime import datetime

def create_media_filename(sender_name, original_filename):
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
    


async def send_whatsapp_message(recipient, text):

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

whatsapp_menu_state = {}

INCOMING = BASE / "incoming"
IMAGES = BASE / "images"
VIDEOS = BASE / "videos"
PRESENTATIONS = BASE / "presentations"
AUDIO = BASE / "audio"
YOUTUBE = BASE / "youtube"
ERROR = BASE / "error"

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

    if size < 1024:
        return f"{size} B"

    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"

    if size < 1024 ** 3:
        return f"{size / (1024 ** 2):.1f} MB"

    return f"{size / (1024 ** 3):.2f} GB"


def format_duration(seconds):

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
    return templates.TemplateResponse(
	request=request,
        name="index.html",
        context={}
        
    )


@app.get("/status")
def status():

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
    VERIFY_TOKEN = "HolyricsMetaWebhook2026"

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)

    return {"error": "Token de verificação inválido"}

@app.post("/webhook/whatsapp")
async def receive_whatsapp_webhook(request: Request):

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

                        if current_menu == "esperando_youtube":

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

                        else:

                            asyncio.create_task(
                                send_whatsapp_message(
                                    sender,
                                    "👋 Olá! Seja bem-vindo ao WhatsApp da Casa de Oração Portinari!\n\n"
                                    "Escolha uma opção:\n\n"
                                    "1️⃣ Horários\n"
                                    "2️⃣ Escalas\n"
                                    "3️⃣ Eventos\n"
                                    "4️⃣ Envio de Mídias\n\n"
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


                        if whatsapp_menu_state.get(sender) != "esperando_imagem":
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
                        extension = mime_type.split("/")[-1] if "/" in mime_type else "jpg"

                        original_filename = f"whatsapp_{media_id}.{extension}"

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
                            "WHATSAPP | Imagem recebida | Arquivo: %s | MIME: %s",
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
    return youtube_progress

@app.post("/youtube", response_class=HTMLResponse)
async def youtube_download(
    url: str = Form(...),
    username: str = Depends(authenticate)
):
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
