import re
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials


# ============================================================
# CONFIGURAÇÃO
# ============================================================

ARQUIVO_CREDENCIAIS = (
    "/opt/holyrics/escala/credentials/"
    "automacao-whatsapp-escala-5013ebff7dcc.json"
)

URL_PLANILHA = (
    "https://docs.google.com/spreadsheets/d/"
    "1dVEJT40FgAv4d9r2fzy7MtjLdWt2MrcihuHTPIV0j40/edit"
)

NOME_ABA = "Eventos"


# ============================================================
# GOOGLE SHEETS
# ============================================================

def conectar_planilha():
    escopos = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    credenciais = Credentials.from_service_account_file(
        ARQUIVO_CREDENCIAIS,
        scopes=escopos,
    )

    cliente = gspread.authorize(credenciais)

    return cliente.open_by_url(URL_PLANILHA)


# ============================================================
# AUXILIARES
# ============================================================

def limpar(texto):
    if texto is None:
        return ""

    return str(texto).strip()


def converter_data(texto):
    """
    Converte uma data no formato DD/MM/AAAA
    para um objeto date.
    """

    texto = limpar(texto)

    if not texto:
        return None

    formatos = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            pass

    return None


def converter_horario(texto):
    """
    Converte horários como:
    20:00
    20:00:00
    """

    texto = limpar(texto)

    if not texto:
        return None

    formatos = [
        "%H:%M:%S",
        "%H:%M",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato).time()
        except ValueError:
            pass

    return None


# ============================================================
# LEITURA DOS EVENTOS
# ============================================================

def carregar_eventos():
    """
    Lê a aba Eventos e retorna somente os eventos ativos.

    Estrutura esperada:

    A = ID
    B = Data
    C = Evento
    D = Horário
    E = Local
    F = Descrição
    G = Ativo
    """

    planilha = conectar_planilha()
    aba = planilha.worksheet(NOME_ABA)

    dados = aba.get_all_records()

    eventos = []

    for linha in dados:

        ativo = limpar(linha.get("Ativo", "")).lower()

        if ativo != "sim":
            continue

        data = converter_data(linha.get("Data", ""))
        horario = converter_horario(linha.get("Horário", ""))

        if not data:
            continue

        evento = {
            "id": limpar(linha.get("ID", "")),
            "data": data,
            "horario": horario,
            "evento": limpar(linha.get("Evento", "")),
            "local": limpar(linha.get("Local", "")),
            "descricao": limpar(linha.get("Descrição", "")),
            "ativo": True,
        }

        eventos.append(evento)

    # Ordena por data e depois por horário
    eventos.sort(
        key=lambda x: (
            x["data"],
            x["horario"] if x["horario"] else datetime.min.time(),
        )
    )

    return eventos


# ============================================================
# CONSULTAS
# ============================================================

def consultar_data(data_texto):
    """
    Consulta eventos de uma determinada data.

    Aceita:
    DD/MM/AAAA
    """

    data = converter_data(data_texto)

    if not data:
        return []

    eventos = carregar_eventos()

    return [
        evento
        for evento in eventos
        if evento["data"] == data
    ]


def consultar_mes(mes_texto):
    """
    Consulta eventos de determinado mês.

    Aceita:
    MM/AAAA
    M/AAAA
    """

    texto = limpar(mes_texto)

    match = re.match(r"^(\d{1,2})/(\d{4})$", texto)

    if not match:
        return []

    mes = int(match.group(1))
    ano = int(match.group(2))

    if mes < 1 or mes > 12:
        return []

    eventos = carregar_eventos()

    return [
        evento
        for evento in eventos
        if evento["data"].month == mes
        and evento["data"].year == ano
    ]


def consultar_todos():
    """
    Retorna todos os eventos ativos.
    """

    return carregar_eventos()

def consultar_proximos():
    """
    Retorna os próximos eventos ativos,
    a partir da data atual.
    """

    hoje = datetime.now().date()

    eventos = carregar_eventos()

    return [
        evento
        for evento in eventos
        if evento["data"] >= hoje
    ]


# ============================================================
# FORMATAÇÃO
# ============================================================

def formatar_evento(evento):

    data = evento["data"].strftime("%d/%m/%Y")

    if evento["horario"]:
        horario = evento["horario"].strftime("%H:%M")
    else:
        horario = ""

    texto = f"📅 {data}\n"

    if horario:
        texto += f"🕐 {horario}\n"

    if evento["evento"]:
        texto += f"🎯 {evento['evento']}\n"

    if evento["local"]:
        texto += f"📍 {evento['local']}\n"

    if evento["descricao"]:
        texto += f"📝 {evento['descricao']}\n"

    return texto.rstrip()


def formatar_eventos(eventos, titulo="📅 EVENTOS"):
    """
    Formata uma lista de eventos para WhatsApp.
    """

    if not eventos:
        return f"{titulo}\n\nNenhum evento encontrado."

    partes = [titulo]

    for evento in eventos:
        partes.append(
            "\n" + formatar_evento(evento)
        )

    return "\n\n".join(partes)
