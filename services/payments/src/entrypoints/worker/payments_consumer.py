"""Entrypoint del worker: consume Payments Queue (SQS) y procesa reembolsos."""

from __future__ import annotations

import logging

from adapters.services.sqs_payments_consumer import SqsPaymentsConsumer


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    consumer = SqsPaymentsConsumer()
    consumer.run_forever()


if __name__ == "__main__":
    main()
