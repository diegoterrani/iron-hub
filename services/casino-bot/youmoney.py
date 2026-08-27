import random

from yoomoney import Authorize, Client, Quickpay
from config import *
from main import sqlite3, InlineKeyboardButton, InlineKeyboardMarkup, bot

async def create_payment_youmoney(amount, chat_id):

    if not yoomoney_receiver:
        raise RuntimeError("YOOMONEY_RECEIVER is not configured")

    quickpay = Quickpay(
        receiver=yoomoney_receiver,
        quickpay_form="shop",
        targets="Sponsor this project",
        paymentType="SB",
        label=str(chat_id) + str(random.randint(100000, 999999)),
        sum=amount,
    )

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('UPDATE payment_youmoney SET bill_id = ? WHERE user_id = ?', (quickpay.label, chat_id,))
    conn.commit()

    check = InlineKeyboardButton('Verificar 🔎', callback_data='check_bill_youmoney')
    pay = InlineKeyboardButton('Pagar 💳', callback_data='pay', url=quickpay.redirected_url)
    youmoney_kb = InlineKeyboardMarkup(row_width=2).add(pay, check)

    cursor.close()

    await bot.send_message(chat_id, f'Valor do depósito: *{amount}* 🪙' , reply_markup=youmoney_kb, parse_mode = 'Markdown')

async def check_payment_youmoney(c, chat_id, message_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bill = cursor.execute('SELECT bill_id FROM payment_youmoney WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    referer = cursor.execute('SELECT referer FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    voucher = cursor.execute('SELECT voucher FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    promo = cursor.execute('SELECT promo FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

    if referer is not None:

        referal_level = cursor.execute('SELECT referal_level FROM users WHERE user_id = ?', (referer,)).fetchone()[0]
        referal_profit = cursor.execute('SELECT referal_profit FROM info WHERE user_id = ?', (referer,)).fetchone()[0]

        client = Client(token_youmoney)
        history = client.operation_history(label=bill)

        if len(history.operations) == 0:

            await c.answer(text='Pagamento não confirmado ❌')

        else:

            await bot.answer_callback_query(c.id)

            for operation in history.operations:

                cursor.execute('UPDATE info SET amount = ? WHERE user_id = ?', (operation.amount, chat_id,))
                conn.commit()

                amount = cursor.execute('SELECT amount FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
                username = cursor.execute('SELECT nickname FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

                if operation.status == 'success':

                    if referer is not None:

                        if voucher:

                            voucher = round(amount) + int(voucher)

                            cursor.execute('UPDATE info SET voucher = ? WHERE user_id = ?', (None, chat_id,))
                            conn.commit()

                        else:

                            voucher = 0

                        if promo:

                            promo = (round(amount) / 100) * promo

                            cursor.execute('UPDATE info SET promo = ? WHERE user_id = ?', (None, chat_id,))
                            conn.commit()

                        else:

                            promo = 0

                        if referal_level == 1:

                            cursor.execute('UPDATE info SET referal_profit = ? WHERE user_id = ?',
                                           (referal_profit + (round(int(amount / 100)) * 2), referer,))
                            conn.commit()

                            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?',
                                           (balance + (round(amount / 100) * 2), referer,))
                            conn.commit()

                            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?',
                                           (balance + round(amount), chat_id,))
                            conn.commit()

                            cursor.execute('UPDATE info SET method = ? WHERE user_id = ?',
                                           ('youmoney', chat_id,))
                            conn.commit()

                            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                            amount = cursor.execute('SELECT amount FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

                            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                        text=f'Depósito confirmado ✅ \n\n Seu saldo: *{balance}* 🪙 \n\n ',
                                                        parse_mode='Markdown')
                            await bot.send_message(admin[0],
                                                   f'💰 Novo depósito \n\n De: \n\n@{username} | {chat_id} \n\n Valor: \n\n*{round(amount)}* 🪙',
                                                   parse_mode='Markdown')
                            cursor.close()

                        elif referal_level == 2:

                            cursor.execute('UPDATE info SET referal_profit = ? WHERE user_id = ?',
                                           (referal_profit + (round(int(amount / 100)) * 4), referer,))
                            conn.commit()

                            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?',
                                           (balance + (round(amount / 100) * 4), referer,))
                            conn.commit()

                            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?',
                                           (balance + round(amount), chat_id,))
                            conn.commit()

                            cursor.execute('UPDATE info SET method = ? WHERE user_id = ?',
                                           ('youmoney', chat_id,))
                            conn.commit()

                            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                            amount = cursor.execute('SELECT amount FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

                            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                        text=f'Depósito confirmado ✅ \n\n Seu saldo: *{balance}* 🪙 \n\n ',
                                                        parse_mode='Markdown')
                            await bot.send_message(admin[0],
                                                   f'💰 Novo depósito \n\n De: \n\n@{username} | {chat_id} \n\n Valor: \n\n*{round(amount)}* 🪙',
                                                   parse_mode='Markdown')
                            cursor.close()

                        elif referal_level == 3:

                            cursor.execute('UPDATE info SET referal_profit = ? WHERE user_id = ?',
                                           (referal_profit + (round(int(amount / 100)) * 6), referer,))
                            conn.commit()

                            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?',
                                           (balance + (round(amount / 100) * 6), referer,))
                            conn.commit()

                            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?',
                                           (balance + round(amount), chat_id,))
                            conn.commit()

                            cursor.execute('UPDATE info SET method = ? WHERE user_id = ?',
                                           ('youmoney', chat_id,))
                            conn.commit()

                            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                            amount = cursor.execute('SELECT amount FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

                            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                        text=f'Depósito confirmado ✅ \n\n Seu saldo: *{balance}* 🪙 \n\n ',
                                                        parse_mode='Markdown')
                            await bot.send_message(admin[0],
                                                   f'💰 Novo depósito \n\n De: \n\n@{username} | {chat_id} \n\n Valor: \n\n*{round(amount)}* 🪙',
                                                   parse_mode='Markdown')
                            cursor.close()

                        elif referal_level == 4:

                            cursor.execute('UPDATE info SET referal_profit = ? WHERE user_id = ?',
                                           (referal_profit + (round(int(amount / 100)) * 8), referer,))
                            conn.commit()

                            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?',
                                           (balance + (round(amount / 100) * 8), referer,))
                            conn.commit()

                            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?',
                                           (balance + round(amount), chat_id,))
                            conn.commit()

                            cursor.execute('UPDATE info SET method = ? WHERE user_id = ?',
                                           ('youmoney', chat_id,))
                            conn.commit()

                            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                            amount = cursor.execute('SELECT amount FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

                            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                        text=f'Depósito confirmado ✅ \n\n Seu saldo: *{balance}* 🪙 \n\n ',
                                                        parse_mode='Markdown')
                            await bot.send_message(admin[0],
                                                   f'💰 Novo depósito \n\n De: \n\n@{username} | {chat_id} \n\n Valor: \n\n*{round(amount)}* 🪙',
                                                   parse_mode='Markdown')
                            cursor.close()

                        elif referal_level == 5:

                            cursor.execute('UPDATE info SET referal_profit = ? WHERE user_id = ?',
                                           (referal_profit + (round(int(amount / 100)) * 10), referer,))
                            conn.commit()

                            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?',
                                           (balance + (round(amount / 100) * 10), referer,))
                            conn.commit()

                            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?',
                                           (balance + round(amount), chat_id,))
                            conn.commit()

                            cursor.execute('UPDATE info SET method = ? WHERE user_id = ?',
                                           ('youmoney', chat_id,))
                            conn.commit()

                            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                            amount = cursor.execute('SELECT amount FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

                            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                        text=f'Depósito confirmado ✅ \n\n Seu saldo: *{balance}* 🪙 \n\n ',
                                                        parse_mode='Markdown')
                            await bot.send_message(admin[0],
                                                   f'💰 Novo depósito \n\n De: \n\n@{username} | {chat_id} \n\n Valor: \n\n*{round(amount)}* 🪙',
                                                   parse_mode='Markdown')
                            cursor.close()

                        else:

                            print('bebra')

                    else:

                        if voucher:

                            voucher = round(amount) + int(voucher)

                            cursor.execute('UPDATE info SET voucher = ? WHERE user_id = ?', (None, chat_id,))
                            conn.commit()

                        else:

                            voucher = 0

                        if promo:

                            promo = (round(amount) / 100) * promo

                            cursor.execute('UPDATE info SET promo = ? WHERE user_id = ?', (None, chat_id,))
                            conn.commit()

                        else:

                            promo = 0

                        cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (balance + amount + promo + voucher, chat_id,))
                        conn.commit()

                        balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                        amount = cursor.execute('SELECT amount FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

                        cursor.execute('UPDATE info SET method = ? WHERE user_id = ?',
                                       ('youmoney', chat_id,))
                        conn.commit()

                        await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                    text=f'Depósito confirmado ✅ \n\n Seu saldo: *{balance}* 🪙 \n\n ',
                                                    parse_mode='Markdown')
                        await bot.send_message(admin[0],
                                               f'💰 Novo depósito \n\n De: \n\n@{username} | {chat_id} \n\n Valor: \n\n*{round(amount)}* 🪙',
                                               parse_mode='Markdown')

                        cursor.close()

                else:

                    await c.answer(text='Pagamento não confirmado ❌')

    else:

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        client = Client(token_youmoney)
        history = client.operation_history(label=bill)

        cursor.close()

        if len(history.operations) == 0:

            await c.answer(text='Pagamento não confirmado ❌')

        else:

            await bot.answer_callback_query(c.id)

            for operation in history.operations:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                cursor.execute('UPDATE info SET amount = ? WHERE user_id = ?', (operation.amount, chat_id,))
                conn.commit()

                amount = cursor.execute('SELECT amount FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
                username = cursor.execute('SELECT nickname FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                if operation.status == 'success':

                    if voucher:

                        voucher = round(amount) + int(voucher)

                        conn = sqlite3.connect('bebra.db', check_same_thread=False)
                        cursor = conn.cursor()

                        cursor.execute('UPDATE info SET voucher = ? WHERE user_id = ?', (None, chat_id,))
                        conn.commit()

                        cursor.close()

                    else:

                        voucher = 0

                    if promo:

                        promo = (round(amount) / 100) * promo

                        conn = sqlite3.connect('bebra.db', check_same_thread=False)
                        cursor = conn.cursor()

                        cursor.execute('UPDATE info SET promo = ? WHERE user_id = ?', (None, chat_id,))
                        conn.commit()

                        cursor.close()

                    else:

                        promo = 0

                    conn = sqlite3.connect('bebra.db', check_same_thread=False)
                    cursor = conn.cursor()

                    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (balance + round(amount) + promo + voucher, chat_id,))
                    conn.commit()

                    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                    amount = cursor.execute('SELECT amount FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

                    cursor.execute('UPDATE info SET method = ? WHERE user_id = ?',
                                   ('youmoney', chat_id,))
                    conn.commit()

                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                text=f'Depósito confirmado ✅ \n\n Seu saldo: *{balance}* 🪙 \n\n ',
                                                parse_mode='Markdown')
                    await bot.send_message(admin[0],
                                           f'💰 Novo depósito \n\n De: \n\n@{username} | {chat_id} \n\n Valor: \n\n*{round(amount)}* 🪙',
                                           parse_mode='Markdown')
                    cursor.close()

                else:

                    await c.answer(text='Pagamento não confirmado ❌')
