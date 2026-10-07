# lavepay

Асинхронный клиент к [Lave Pay](https://laveshka.io/docs/lave-pay). Счета, выплаты, вебхуки. Если вебхук поднимать негде, статусы можно опрашивать самим.

```bash
pip install lavepay
```

Дополнительно, если нужно:

```bash
pip install "lavepay[fastapi]"    # приём вебхука
pip install "lavepay[aiogram]"    # кнопка оплаты в боте
pip install "lavepay[aiohttp]"    # тот же вебхук на aiohttp
pip install "lavepay[qr]"         # PNG со ссылкой
```

Ключ берётся при создании мерчанта, один раз. Переменная `LAVEPAY_API_KEY`, адрес по умолчанию `https://api.laveshka.io/merchant/v1`.

Суммы передавайте `Decimal` или строкой. `float` библиотека не примет.

## Счёт

```python
import asyncio
from decimal import Decimal
from lavepay import LavePay

async def main():
    async with LavePay("LAVE-12-...") as lp:
        invoice = await lp.invoices.create(
            Decimal("12.34"),
            order_id="ord-1042",
            description="Набор стикеров",
        )
        print(invoice.pay_url)

asyncio.run(main())
```

Повтор с тем же `order_id` и той же суммой вернёт тот же счёт. Для выплат ключ свой, и его лучше собирать из заказа, а не случайно:

```python
from lavepay import idempotency_key

key = idempotency_key("bonus", user_id, "2026-08-22")
await lp.transfers.create("@durov", "5.00", idempotency_key=key)
```

Перед тем как отдать товар, сверьте не только статус:

```python
if invoice.matches(amount="12.34", order_id="ord-1042"):
    ...
```

## Поллинг

Один обработчик и для вебхука, и для опроса. Схема как в aiosend: повесили функцию, поставили объект в очередь, запустили цикл.

```python
from lavepay import LavePay

lp = LavePay("LAVE-12-...")

@lp.invoice_paid()
async def paid(invoice, message):
    if invoice.matches(order_id=message.text):
        await message.answer("оплачено")

async def checkout(message):
    invoice = await lp.invoices.create("12.34", order_id=str(message.message_id))
    invoice.poll(message=message)

# await lp.start_polling()
# lp.stop_polling()
```

`discover=True` сам смотрит открытые счета и выплаты, без `poll()` на каждый. Первый круг только запоминает, что уже висит, и старые оплаты заново не присылает.

```python
await lp.start_polling(discover=True)
```

По умолчанию объект спрашивается, пока API само его не закроет. Свой предел — `PollingConfig(timeout=3600)`, по нему придёт `invoice_timeout`. Частота запросов ограничена (`max_rps=2`), у ключа лимит 300 в минуту.

Один и тот же статус второй раз обработчику не отдаётся. Память процессная: после рестарта событие может прийти снова, `matches` от этого и нужен.

## FastAPI

На ответ вебхуку есть 10 секунд, поэтому маршрут отвечает `200` сразу, а обработчики идут следом. Подпись считается по сырому телу. Если сначала вызвать `request.json()`, она не сойдётся.

```python
from fastapi import FastAPI
from lavepay import LavePay
from lavepay.integrations.fastapi import install

app = FastAPI()
lp = LavePay("LAVE-12-...", webhook_secret="whsec_...")

@lp.invoice_paid()
async def paid(invoice):
    ...

install(app, lp)  # POST /lavepay
```

Клиент ляжет в `app.state.lavepay` и закроется вместе с приложением.

## aiogram

Это не Telegram Payments и не `sendInvoice`. Покупателю уходит ссылка в мини-приложение.

```python
import asyncio
from aiogram import Bot, Dispatcher
from lavepay import LavePay
from lavepay.integrations.aiogram import install, pay_keyboard

lp = LavePay("LAVE-12-...")
bot = Bot("123:ABC")
dp = Dispatcher()
install(dp, lp)  # поллинг стартует и гаснет вместе с ботом

@dp.message()
async def pay(message):
    invoice = await lp.invoices.create("12.34", order_id=str(message.message_id))
    invoice.poll(message=message)
    await message.answer(
        "К оплате",
        reply_markup=pay_keyboard(invoice, check="Проверить оплату"),
    )

@lp.invoice_paid()
async def paid(invoice, message):
    await message.answer("оплачено")
```

«Проверить оплату» только говорит, ждёт счёт или уже оплачен. Товар по этой кнопке не выдавайте: его выдаёт `invoice_paid`, иначе заказ уйдёт дважды.

Если бот и так принимает апдейты вебхуком на aiohttp, туда же можно повесить Lave Pay, тогда опрос не нужен:

```python
install(dp, lp, aiohttp_app=app)
```

## Ошибки

Код исключения совпадает с `error.code` в ответе: `InsufficientFundsError`, `RateChangedError`, `QuoteExpiredError` и остальные. `explain(error)` — короткая фраза, её можно показать человеку. Текст сервера туда не попадает.

## Выкладка

Собрать локально:

```bash
python -m build
```

На PyPI пакет уезжает тегом `v0.1.0`. Цифра должна совпасть с `lavepay.__version__`, иначе CI остановится до публикации. Workflow `ci.yml` гоняет тесты, собирает пакет и отдаёт его PyPI через trusted publisher, без токенов. На PyPI он указывается один раз: этот репозиторий, workflow `ci.yml`, окружение `pypi`.

## Лицензия

MIT.
