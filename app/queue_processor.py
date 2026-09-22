from pathlib import Path
import shutil
import logging
import socket

INCOMING = Path("/data/incoming")
APPROVED = Path("/data/approved")
WINDOWS_ENTRY = Path("/windows/entrada")

WINDOWS_IP = "192.168.18.39"
SMB_PORT = 445
SMB_TIMEOUT = 3


logging.basicConfig(
    filename="/logs/queue_processor.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def windows_available():
    try:
        with socket.create_connection(
            (WINDOWS_IP, SMB_PORT),
            timeout=SMB_TIMEOUT
        ):
            return True

    except OSError:
        return False


def process_queue():

    files = [
        f for f in INCOMING.iterdir()
        if f.is_file()
	and not f.name.endswith(".part")
    ]

    if not files:
        print("Fila vazia.", flush=True)
        return

    if not windows_available():
        print(
            "Windows indisponível. Arquivos permanecem em incoming.",
            flush=True
        )

        logging.warning(
            "Windows indisponível. Nenhuma transferência realizada."
        )

        return

    for source in files:

        destination = WINDOWS_ENTRY / source.name

        print(
            f"Processando: {source.name}",
            flush=True
        )

        if destination.exists():

            print(
                "Arquivo já existe no Windows. Pulando para o próximo.",
                flush=True
            )

            logging.warning(
                "Arquivo já existe no destino: %s",
                source.name
            )

            continue

        try:

            shutil.copy2(
                source,
                destination
            )

            if not destination.exists():
                raise RuntimeError(
                    "Arquivo não apareceu no destino."
                )

            if destination.stat().st_size != source.stat().st_size:
                raise RuntimeError(
                    "Tamanho do arquivo diferente após a cópia."
                )

            source.unlink()

            print(
                "Arquivo removido do Raspberry após transferência confirmada.",
                flush=True
            )

            logging.info(
                "Arquivo removido do Raspberry após transferência: %s",
                source.name
            )

            print("Transferência concluída.", flush=True)

            logging.info(
                "Arquivo transferido com sucesso: %s",
                source.name
            )

        except Exception as error:

            print(
                f"Erro: {error}",
                flush=True
            )

            logging.error(
                "Erro ao processar %s: %s",
                source.name,
                error
            )


if __name__ == "__main__":
    process_queue()
