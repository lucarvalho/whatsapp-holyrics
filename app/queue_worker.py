import time
import logging

from queue_processor import process_queue


logging.basicConfig(
    filename="/logs/queue_worker.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


while True:
    try:
        process_queue()

    except Exception as error:
        logging.exception(
            "Erro inesperado no processador: %s",
            error
        )

    time.sleep(30)
