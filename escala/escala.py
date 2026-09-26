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

NOME_ABA = "Julho-Outubro-2026"

MESES = {
    "JANEIRO": 1,
    "FEVEREIRO": 2,
    "MARÇO": 3,
    "MARCO": 3,
    "ABRIL": 4,
    "MAIO": 5,
    "JUNHO": 6,
    "JULHO": 7,
    "AGOSTO": 8,
    "SETEMBRO": 9,
    "OUTUBRO": 10,
    "NOVEMBRO": 11,
    "DEZEMBRO": 12,
}


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
    """Remove espaços extras."""
    if texto is None:
        return ""

    return str(texto).strip()


def nome_valido(texto):
    """Verifica se existe um nome/evento preenchido."""
    texto = limpar(texto)

    if not texto:
        return False

    return True


def adicionar_registro(
    registros,
    ano,
    mes,
    dia,
    tipo,
    dirigente="",
    pregador="",
):
    """
    Adiciona um registro normalizado.
    """

    if not dia:
        return

    try:
        dia_int = int(str(dia).strip())
    except ValueError:
        return

    try:
        data = datetime(ano, mes, dia_int).date()
    except ValueError:
        return

    dirigente = limpar(dirigente)
    pregador = limpar(pregador)

    # Só adiciona se houver alguma informação de escala.
    if not dirigente and not pregador:
        return

    registros.append(
        {
            "data": data,
            "tipo": tipo,
            "dirigente": dirigente,
            "pregador": pregador,
        }
    )


# ============================================================
# PARSER
# ============================================================

def carregar_escala():
    """
    Lê a planilha e transforma o primeiro bloco em registros
    independentes.

    O segundo bloco da planilha é uma cópia do primeiro e,
    portanto, não é processado.
    """

    planilha = conectar_planilha()
    aba = planilha.worksheet(NOME_ABA)

    dados = aba.get_all_values()

    registros = []

    ano_atual = None
    mes_atual = None

    # O primeiro bloco termina antes da segunda ocorrência
    # de "ESCALA - JD PORTINARI".
    bloco_final = len(dados)

    primeira_escala = False

    for indice, linha in enumerate(dados):

        # ----------------------------------------------------
        # Identifica o início do segundo bloco
        # ----------------------------------------------------
        primeira_celula = limpar(linha[1]) if len(linha) > 1 else ""

        if primeira_celula == "ESCALA - JD PORTINARI":
            if primeira_escala:
                bloco_final = indice
                break

            primeira_escala = True
            continue

        # ----------------------------------------------------
        # Só processa o primeiro bloco
        # ----------------------------------------------------
        if not primeira_escala or indice >= bloco_final:
            continue

        # ----------------------------------------------------
        # Identifica mês/ano
        # Exemplo: SETEMBRO | 2026
        # ----------------------------------------------------
        match_mes = re.match(
            r"^([A-ZÇÃÕ]+)\s*\|\s*(\d{4})$",
            primeira_celula.upper(),
        )

        if match_mes:
            nome_mes = match_mes.group(1).strip()
            ano_atual = int(match_mes.group(2))

            if nome_mes in MESES:
                mes_atual = MESES[nome_mes]

            continue

        # Ainda não temos mês/ano
        if not ano_atual or not mes_atual:
            continue

        # ----------------------------------------------------
        # Precisamos de pelo menos 12 colunas úteis
        # ----------------------------------------------------
        linha = linha + [""] * (12 - len(linha))

        # Colunas:
        #
        # 1  = Escola Dominical - Dia
        # 2  = Escola Dominical - Dirigente
        #
        # 4  = Domingo Noite - Dirigente
        # 5  = Domingo Noite - Pregador
        #
        # 6  = Quarta-feira - Dia
        # 7  = Quarta-feira - Dirigente
        # 8  = Quarta-feira - Pregador
        #
        # 9  = Sábado - Dia
        # 10 = Sábado - Dirigente
        # 11 = Sábado - Pregador

        dia_escola = limpar(linha[1])
        dirigente_escola = limpar(linha[2])

        dirigente_domingo = limpar(linha[4])
        pregador_domingo = limpar(linha[5])

        dia_quarta = limpar(linha[6])
        dirigente_quarta = limpar(linha[7])
        pregador_quarta = limpar(linha[8])

        dia_sabado = limpar(linha[9])
        dirigente_sabado = limpar(linha[10])
        pregador_sabado = limpar(linha[11])

        # ----------------------------------------------------
        # Escola Dominical
        # ----------------------------------------------------
        adicionar_registro(
            registros,
            ano_atual,
            mes_atual,
            dia_escola,
            "Escola Dominical",
            dirigente_escola,
            "",
        )

        # ----------------------------------------------------
        # Domingo à noite
        #
        # O dia é o mesmo da Escola Dominical da mesma linha.
        # ----------------------------------------------------
        if dia_escola and (
            nome_valido(dirigente_domingo)
            or nome_valido(pregador_domingo)
        ):
            adicionar_registro(
                registros,
                ano_atual,
                mes_atual,
                dia_escola,
                "Domingo à noite",
                dirigente_domingo,
                pregador_domingo,
            )

        # ----------------------------------------------------
        # Quarta-feira
        # ----------------------------------------------------
        adicionar_registro(
            registros,
            ano_atual,
            mes_atual,
            dia_quarta,
            "Quarta-feira",
            dirigente_quarta,
            pregador_quarta,
        )

        # ----------------------------------------------------
        # Sábado
        # ----------------------------------------------------
        adicionar_registro(
            registros,
            ano_atual,
            mes_atual,
            dia_sabado,
            "Sábado",
            dirigente_sabado,
            pregador_sabado,
        )

    # Ordena cronologicamente


    ordem_tipos = {
        "Escola Dominical": 1,
        "Domingo à noite": 2,
        "Quarta-feira": 3,
        "Sábado": 4,
    }

    registros.sort(
        key=lambda registro: (
            registro["data"],
            ordem_tipos.get(registro["tipo"], 99),
        )
    )


    return registros


# ============================================================
# CONSULTA POR DATA
# ============================================================

def consultar_data(data_texto):
    """
    Consulta uma data no formato DD/MM/AAAA.
    """

    try:
        data = datetime.strptime(
            data_texto.strip(),
            "%d/%m/%Y",
        ).date()
    except ValueError:
        return []

    registros = carregar_escala()

    return [
        registro
        for registro in registros
        if registro["data"] == data
    ]


# ============================================================
# CONSULTA POR NOME
# ============================================================

def consultar_nome(nome):
    """
    Procura parcialmente o nome em Dirigente e Pregador.
    """

    nome = limpar(nome).lower()

    if not nome:
        return []

    registros = carregar_escala()

    resultado = []

    for registro in registros:

        dirigente = registro["dirigente"].lower()
        pregador = registro["pregador"].lower()

        if nome in dirigente or nome in pregador:
            resultado.append(registro)

    return resultado

# ============================================================
# CONSULTA POR MÊS
# ============================================================

def consultar_mes(mes_texto):
    """
    Consulta todos os serviços de um mês.
    Aceita MM/AAAA ou M/AAAA.
    """

    try:
        partes = mes_texto.strip().split("/")

        if len(partes) != 2:
            return []

        mes = int(partes[0])
        ano = int(partes[1])

        if mes < 1 or mes > 12:
            return []

    except ValueError:
        return []

    registros = carregar_escala()

    return [
        registro
        for registro in registros
        if (
            registro["data"].month == mes
            and registro["data"].year == ano
        )
    ]


# ============================================================
# CONSULTA DE INTERCÂMBIO
# ============================================================

def consultar_intercambio(mes_texto):
    """
    Consulta o intercâmbio do último sábado de um mês.
    """

    registros = consultar_mes(mes_texto)

    sabados = [
        registro
        for registro in registros
        if registro["tipo"] == "Sábado"
    ]

    if not sabados:
        return []

    ultima_data = max(
        registro["data"]
        for registro in sabados
    )

    return [
        registro
        for registro in sabados
        if registro["data"] == ultima_data
    ]

# ============================================================
# TESTE
# ============================================================

def formatar_registro_whatsapp(registro):
    data = registro["data"].strftime("%d/%m/%Y")

    linhas = [
        f"📅 {data}",
        f"📌 {registro['tipo']}",
    ]

    if registro["dirigente"]:
        linhas.append(
            f"🙋 Dirigente: {registro['dirigente']}"
        )

    if registro["pregador"]:
        linhas.append(
            f"🎤 Pregador: {registro['pregador']}"
        )

    return "\n".join(linhas)


def formatar_escala_data(data_texto):
    resultados = consultar_data(data_texto)

    if not resultados:
        return (
            f"❌ Nenhuma escala encontrada para "
            f"{data_texto}."
        )

    linhas = [
        f"📅 *ESCALA — {data_texto}*",
        "",
    ]

    for registro in resultados:
        linhas.append(
            formatar_registro_whatsapp(registro)
        )
        linhas.append("")

    return "\n".join(linhas).strip()


def formatar_escala_nome(nome):
    resultados = consultar_nome(nome)

    if not resultados:
        return (
            f"❌ Nenhuma escala encontrada para "
            f"*{nome}*."
        )

    linhas = [
        f"🔎 *ESCALA DE: {nome.upper()}*",
        "",
    ]

    for registro in resultados:
        linhas.append(
            formatar_registro_whatsapp(registro)
        )
        linhas.append("")

    return "\n".join(linhas).strip()

# ============================================================
# FORMATAÇÃO DA CONSULTA POR MÊS
# ============================================================

def formatar_escala_mes(mes_texto):
    resultados = consultar_mes(mes_texto)

    if not resultados:
        return (
            f"❌ Nenhuma escala encontrada para "
            f"*{mes_texto}*."
        )

    try:
        partes = mes_texto.strip().split("/")
        mes = int(partes[0])
        ano = int(partes[1])

        nomes_meses = [
            "",
            "JANEIRO",
            "FEVEREIRO",
            "MARÇO",
            "ABRIL",
            "MAIO",
            "JUNHO",
            "JULHO",
            "AGOSTO",
            "SETEMBRO",
            "OUTUBRO",
            "NOVEMBRO",
            "DEZEMBRO",
        ]

        nome_mes = nomes_meses[mes]

    except (ValueError, IndexError):
        nome_mes = mes_texto.upper()
        ano = ""

    linhas = [
        f"📅 *ESCALA — {nome_mes}/{ano}*",
        "",
    ]

    data_anterior = None

    for registro in resultados:

        data = registro["data"]

        if data != data_anterior:

            if data_anterior is not None:
                linhas.append("")

            linhas.append(
                f"📅 *{data.strftime('%d/%m/%Y')}*"
            )

            data_anterior = data

        linhas.append(
            f"📌 {registro['tipo']}"
        )

        if registro["dirigente"]:
            linhas.append(
                f"🙋 Dirigente: {registro['dirigente']}"
            )

        if registro["pregador"]:
            linhas.append(
                f"🎤 Pregador: {registro['pregador']}"
            )

    return "\n".join(linhas)


# ============================================================
# FORMATAÇÃO DO INTERCÂMBIO
# ============================================================

def formatar_intercambio(mes_texto):
    resultados = consultar_intercambio(mes_texto)

    if not resultados:
        return (
            f"❌ Nenhum intercâmbio encontrado "
            f"para *{mes_texto}*."
        )

    registro = resultados[0]

    data = registro["data"].strftime("%d/%m/%Y")

    descricao = registro["dirigente"]

    if not descricao:
        descricao = "Intercâmbio"

    return (
        f"🔄 *INTERCÂMBIO*\n\n"
        f"📅 Data: {data}\n"
        f"📍 {descricao}"
    )


def formatar_escala_completa():
    registros = carregar_escala()

    if not registros:
        return "❌ Nenhuma escala encontrada."

    linhas = [
        "📅 *ESCALA COMPLETA*",
        "",
    ]

    data_anterior = None

    for registro in registros:
        data = registro["data"]

        if data != data_anterior:
            if data_anterior is not None:
                linhas.append("")

            linhas.append(
                f"📅 *{data.strftime('%d/%m/%Y')}*"
            )

            data_anterior = data

        linhas.append(
            f"\n📌 {registro['tipo']}"
        )

        if registro["dirigente"]:
            linhas.append(
                f"🙋 Dirigente: {registro['dirigente']}"
            )

        if registro["pregador"]:
            linhas.append(
                f"🎤 Pregador: {registro['pregador']}"
            )

    return "\n".join(linhas)

if __name__ == "__main__":

    registros = carregar_escala()

    print()
    print("==========================================")
    print(" ESCALA DE SERVIÇOS")
    print("==========================================")
    print()
    print(f"Total de registros: {len(registros)}")
    print()

    for registro in registros:
        data = registro["data"].strftime("%d/%m/%Y")

        print(
            f"{data} | "
            f"{registro['tipo']} | "
            f"Dirigente: {registro['dirigente']} | "
            f"Pregador: {registro['pregador']}"
        )

# ============================================================
# FORMATAÇÃO DE TODOS OS INTERCÂMBIOS
# ============================================================

def formatar_intercambios():
    """
    Mostra o intercâmbio do último sábado
    de cada mês da escala.
    """

    meses = [
        ("07/2026", "JULHO"),
        ("08/2026", "AGOSTO"),
        ("09/2026", "SETEMBRO"),
        ("10/2026", "OUTUBRO"),
    ]

    linhas = [
        "🔄 *INTERCÂMBIOS*",
        "",
    ]

    encontrou = False

    for mes_texto, nome_mes in meses:

        resultados = consultar_intercambio(mes_texto)

        if not resultados:
            continue

        encontrou = True

        registro = resultados[0]

        data = registro["data"].strftime("%d/%m/%Y")

        descricao = registro["dirigente"]

        if not descricao:
            descricao = "Intercâmbio"

        linhas.append(
            f"📅 *{nome_mes}/2026*"
        )

        linhas.append(
            f"Data: {data}"
        )

        linhas.append(
            f"📍 {descricao}"
        )

        linhas.append("")

    if not encontrou:
        return "❌ Nenhum intercâmbio encontrado."

    return "\n".join(linhas).rstrip()
