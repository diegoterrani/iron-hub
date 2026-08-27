from main import *
from config import *
import asyncio
import sqlite3
values = []

async def add_user_with_referal(chat_id, refer, nickname):

    info_list = [chat_id, nickname, bill_id, amount, bet, game, referal_profit, ban, method, voucher, promo, winning]
    user_list = [chat_id, nickname, balance, referals_, photo_id, text, auto_output, refer, referal_level]
    demo_list = [chat_id, 0, 0, 0]

    payment_list = [chat_id, nickname, None, None]

    conn = sqlite3.connect('bebra.db')
    cursor = conn.cursor()

    cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ;", user_list)
    conn.commit()

    cursor.execute("INSERT INTO payment_youmoney VALUES (?, ?, ?, ?) ;", payment_list)
    conn.commit()

    cursor.execute("INSERT INTO payment_bitcoin VALUES (?, ?, ?, ?) ;", payment_list)
    conn.commit()

    cursor.execute("INSERT INTO payment_qiwi VALUES (?, ?, ?, ?) ;", payment_list)
    conn.commit()

    cursor.execute("INSERT INTO payment_crystalpay VALUES (?, ?, ?, ?) ;", payment_list)
    conn.commit()

    cursor.execute("INSERT INTO demo VALUES (?, ?, ?, ?) ;", demo_list)
    conn.commit()

    cursor.execute("INSERT INTO info VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ;", info_list)
    conn.commit()

    referals = cursor.execute('SELECT referals FROM users WHERE user_id = ?', (refer,)).fetchone()[0]
    cursor.execute("UPDATE users SET referals = ? WHERE user_id = ?", (referals + 1, refer,))
    conn.commit()
    referals_of_referer = cursor.execute('SELECT referals FROM users WHERE user_id = ?', (refer,)).fetchone()[0]

    cursor.execute("UPDATE users SET referer = ? WHERE user_id = ?", (refer, chat_id,))
    conn.commit()

    if referals_of_referer <= 10:

        cursor.execute("UPDATE users SET referal_level = ? WHERE user_id = ?", (1, refer,))
        conn.commit()

    elif 20 >= referals_of_referer <= 11:

        cursor.execute("UPDATE users SET referal_level = ? WHERE user_id = ?", (2, refer,))
        conn.commit()

    elif 30 >= referals_of_referer <= 21:

        cursor.execute("UPDATE users SET referal_level = ? WHERE user_id = ?", (3, refer,))
        conn.commit()

    elif 40 >= referals_of_referer <= 31:

        cursor.execute("UPDATE users SET referal_level = ? WHERE user_id = ?", (4, refer,))
        conn.commit()

    elif 50 >= referals_of_referer <= 41:

        cursor.execute("UPDATE users SET referal_level = ? WHERE user_id = ?", (5, refer,))
        conn.commit()

    else:

        cursor.execute("UPDATE users SET referal_level = ? WHERE user_id = ?", (5, refer,))
        conn.commit()

    cursor.close()
    await bot.send_message(chat_id, 'Bem-vindo 👋', reply_markup=kb)

async def add_user(chat_id, nickname):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    info_list = [chat_id, nickname, bill_id, amount, bet, game, referal_profit, ban, method, voucher, promo, winning]
    user_list = [chat_id, nickname, balance, referals_, photo_id, text, auto_output, referer, referal_level]
    payment_list = [chat_id, nickname, None, None]
    demo_list = [chat_id, 0, 0, 0]

    cursor.execute("INSERT INTO payment_youmoney VALUES (?, ?, ?, ?) ;", payment_list)
    conn.commit()

    cursor.execute("INSERT INTO payment_bitcoin VALUES (?, ?, ?, ?) ;", payment_list)
    conn.commit()

    cursor.execute("INSERT INTO payment_qiwi VALUES (?, ?, ?, ?) ;", payment_list)
    conn.commit()

    cursor.execute("INSERT INTO payment_crystalpay VALUES (?, ?, ?, ?) ;", payment_list)
    conn.commit()

    cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ;", user_list)
    conn.commit()

    cursor.execute("INSERT INTO demo VALUES (?, ?, ?, ?) ;", demo_list)
    conn.commit()

    cursor.execute("INSERT INTO info VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ;", info_list)
    conn.commit()

    cursor.close()
    await bot.send_message(chat_id, 'Bem-vindo 👋', reply_markup=kb)

async def sending(message):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    photo = cursor.execute('SELECT photo_id FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
    text = cursor.execute('SELECT text FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

    try:

        for i in cursor.execute('SELECT user_id from users'):

            await asyncio.sleep(0.4)

            if i[0] in admin:

                continue

            else:

                await bot.send_photo(chat_id=i[0], photo=photo, caption=text, parse_mode='Markdown')

    except:

        pass

    cursor.close()

    await bot.send_message(message.chat.id, 'Envio concluído ✅')

async def users_actions(chat_id, message_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    data = []
    ban_data = []

    for i in cursor.execute('SELECT user_id FROM info WHERE ban = 1').fetchall():

        info = await bot.get_chat_member(user_id = (i[0]), chat_id=i[0])

        if info['user']['username'] == None:

            ban_data.append('<b>' + str(i[0]) + '</b> | ' + f'<b>{i[1]}</b> 🪙')

        else:

            ban_data.append('@' + info['user']['username'] + ' | ' + f'<b>{i[1]}</b> 🪙')

    cursor.close()

    url = 'https://telegra.ph/file/41c1b99e5600a240798ea.jpg'

    if len(ban_data) == 0:

        ban_data = 'Nenhum usuário banido 🔎'

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                    text=f'{hide_link(url)}<b>Usuários banidos</b> 🚫 \n\n' + ban_data,
                                    reply_markup=user_actions_kb, parse_mode='HTML')

    else:

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                    text=f'{hide_link(url)}<b>Usuários banidos</b> 🚫 \n\n' + ('\n'.join(ban_data)),
                                    reply_markup=user_actions_kb, parse_mode='HTML')

async def promocode_action(chat_id, message_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    cur = cursor.fetchone()

    data_good = []

    for i in cursor.execute(
            'SELECT promo, usage_actual, usage_max, percent FROM promocode WHERE usage_actual < usage_max ').fetchall():
        data_good.append(str(i))

    a = ((((('\n'.join(''.join(str(elems)) for elems in data_good))).replace(',', ' |')).replace('(', '')).replace(')',
                                                                                                           '')).replace(
        "'", '')

    if len(a) == 0:

        a = 'Nenhum cupom encontrado 🔎'

    url = 'https://telegra.ph/file/49e0ab25467afd657e68f.jpg'

    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                text=f'{hide_link(url)}<b>Cupons ativos 🎫</b> \n\n' + (a),
                                reply_markup=promocode_kb, parse_mode='HTML')

    cursor.close()

async def voucher_action(chat_id, message_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    cur = cursor.fetchone()

    data_good = []

    for i in cursor.execute(
            'SELECT voucher, usage_actual, usage_max, amount FROM voucher WHERE usage_actual < usage_max ').fetchall():
        data_good.append(str(i))

    a = ((((('\n'.join(''.join(str(elems)) for elems in data_good))).replace(',', ' |')).replace('(', '')).replace(')',
                                                                                                           '')).replace(
        "'", '')

    url = 'https://telegra.ph/file/22a9ee40f9f38c20fb856.jpg'

    if len(a) == 0:

        a = 'Nenhum cupom encontrado 🔎'

    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                text=f'{hide_link(url)}<b>Vouchers ativos 🎟</b> \n\n' + (a),
                                reply_markup = voucher_kb, parse_mode='HTML')
    cursor.close()

async def delete_promo(chat_id, name):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('DELETE FROM promocode WHERE promo = ?', (name,))
    conn.commit()

    await bot.send_message(chat_id, f'Cupom *{name}* removido ✅', reply_markup = back_promocode_kb, parse_mode = 'Markdown')

async def delete_voucher(chat_id, name):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('DELETE FROM voucher WHERE voucher = ?', (name,))
    conn.commit()

    await bot.send_message(chat_id, f'Voucher *{name}* removido ✅', reply_markup = back_voucher_kb, parse_mode = 'Markdown')

async def use_promo(chat_id, msg):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    promo = cursor.execute('SELECT promo FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if promo is not None:

        await bot.send_message(chat_id, 'Você já tem um cupom ativo ❌')

    else:

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        usage_actual = cursor.execute('SELECT usage_actual FROM promocode WHERE promo = ?', (msg,)).fetchone()[0]
        percent = cursor.execute('SELECT percent FROM promocode WHERE promo = ?', (msg,)).fetchone()[0]

        cursor.execute('UPDATE promocode SET usage_actual = ? WHERE promo = ?', (usage_actual + 1, msg,))
        conn.commit()

        cursor.execute('UPDATE info SET promo = ? WHERE user_id = ?', (percent, chat_id))
        conn.commit()

        usage_actual = cursor.execute('SELECT usage_actual FROM promocode WHERE promo = ?', (msg,)).fetchone()[0]
        usage_max = cursor.execute('SELECT usage_max FROM promocode WHERE promo = ?', (msg,)).fetchone()[0]

        if usage_actual >= usage_max:

            cursor.execute('DELETE FROM promocode WHERE promo = ?', (msg,))
            conn.commit()

        else:

            pass

        await bot.send_message(chat_id, f'Cupom *{msg}* ativado ✅'
                                        f'\n\n*+{percent}%* no próximo depósito', parse_mode = 'Markdown')

        cursor.close()

async def use_voucher(chat_id, msg):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    promo = cursor.execute('SELECT voucher FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if promo is not None:

        await bot.send_message(chat_id, 'Você já tem um voucher ativo ❌')

    else:

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        usage_actual = cursor.execute('SELECT usage_actual FROM voucher WHERE voucher = ?', (msg,)).fetchone()[0]
        percent = cursor.execute('SELECT amount FROM voucher WHERE voucher = ?', (msg,)).fetchone()[0]

        cursor.execute('UPDATE voucher SET usage_actual = ? WHERE voucher = ?', (usage_actual + 1, msg,))
        conn.commit()

        cursor.execute('UPDATE info SET voucher = ? WHERE user_id = ?', (percent, chat_id))
        conn.commit()

        usage_actual = cursor.execute('SELECT usage_actual FROM voucher WHERE voucher = ?', (msg,)).fetchone()[0]
        usage_max = cursor.execute('SELECT usage_max FROM voucher WHERE voucher = ?', (msg,)).fetchone()[0]

        if usage_actual >= usage_max:

            cursor.execute('DELETE FROM voucher WHERE voucher = ?', (msg,))
            conn.commit()

        else:

            pass

        await bot.send_message(chat_id, f'Voucher *{msg}* ativado ✅'
                                        f'\n\n*+{percent} 🪙* no próximo depósito', parse_mode='Markdown')

        cursor.close()

async def ban_user_action(chat_id, bot, user):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    if user.isnumeric == False:

        ban = cursor.execute('SELECT ban FROM info WHERE nickname = ?', (user,)).fetchone()[0]

    else:

        ban = cursor.execute('SELECT ban FROM info WHERE user_id = ?', (user,)).fetchone()[0]

    cursor.close()

    if ban == 0:

        if user.isnumeric == False:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute('UPDATE info SET ban = ? WHERE nickname = ?', (1, user,))
            conn.commit()

            cursor.close()

            await bot.send_message(chat_id, f'Usuário @{user} banido ✅', reply_markup=back_admin_panel_kb)

        else:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute('UPDATE info SET ban = ? WHERE user_id = ?', (1, user,))
            conn.commit()

            cursor.close()

            await bot.send_message(chat_id, f'Usuário *{user}* banido ✅',
                                   reply_markup=back_admin_panel_kb, parse_mode = 'Markdown')

    else:

        await bot.send_message(chat_id, 'Usuário já está banido ⚠', reply_markup=back_users_kb)

async def unban_user_action(chat_id, bot, user):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    if user.isnumeric == False:

        ban = cursor.execute('SELECT ban FROM info WHERE nickname = ?', (user,)).fetchone()[0]

    else:

        ban = cursor.execute('SELECT ban FROM info WHERE user_id = ?', (user,)).fetchone()[0]

    cursor.close()

    if ban == 1:

        if user.isnumeric == False:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute('UPDATE info SET ban = ? WHERE nickname = ?', (1, user,))
            conn.commit()

            chat = cursor.execute('SELECT user_id FROM info WHERE nickname = ?', (user,)).fetchone()[0]

            cursor.close()

            await bot.send_message(chat_id, f'Usuário @{user} desbanido ✅', reply_markup=back_admin_panel_kb)
            await bot.send_message(chat, f'Você foi desbanido. Envie /start ✅')

        else:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute('UPDATE info SET ban = ? WHERE user_id = ?', (0, user,))
            conn.commit()

            cursor.close()

            await bot.send_message(chat_id, f'Usuário *{user}* desbanido ✅',
                                   reply_markup=back_admin_panel_kb, parse_mode = 'Markdown')
            await bot.send_message(user, f'Você foi desbanido. Envie /start ✅', reply_markup=back_admin_panel_kb)

    else:

        await bot.send_message(chat_id, 'Usuário não está banido ⚠', reply_markup=back_users_kb)


async def user_increase_balance(chat_id, user, amount):

    if user.isnumeric():

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user,)).fetchone()[0]

        cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (balance + int(amount), user,))
        conn.commit()

        cursor.close()

        await bot.send_message(chat_id, f'Saldo de <b>{user}</b> creditado em <b>{amount}</b> 🪙 ✅',
                               reply_markup=back_admin_panel_kb, parse_mode='HTML')

    else:

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        balance = cursor.execute('SELECT balance FROM users WHERE nickname = ?', (user,)).fetchone()[0]

        cursor.execute('UPDATE users SET balance = ? WHERE nickname = ?', (balance + int(amount), user,))
        conn.commit()

        cursor.close()

        await bot.send_message(chat_id, f'Saldo de @{user} creditado em <b>{amount}</b> 🪙 ✅',
                               reply_markup=back_admin_panel_kb, parse_mode='HTML')


async def user_decrease_balance(chat_id, user, amount):

    if user.isnumeric():

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user,)).fetchone()[0]

        cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (balance - int(amount), user,))
        conn.commit()

        cursor.close()

        await bot.send_message(chat_id, f'Do saldo de <b>{user}</b> debitado <b>{amount}</b>🪙 ✅',
                               reply_markup=back_admin_panel_kb, parse_mode="HTML")

    else:

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        balance = cursor.execute('SELECT balance FROM users WHERE nickname = ?', (user,)).fetchone()[0]

        cursor.execute('UPDATE users SET balance = ? WHERE nickname = ?', (balance - int(amount), user,))
        conn.commit()

        cursor.close()

        await bot.send_message(chat_id, f'Do saldo de @{user} debitado <b>{amount}</b>🪙 ✅',
                               reply_markup=back_admin_panel_kb, parse_mode='HTML')


async def add_admin(chat_id, user_nickname):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    if user_nickname.isnumeric() == True:

        try:

            is_admin = cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_nickname,)).fetchone()[0]

            await bot.send_message(chat_id, f'Usuário *{user_nickname}* já é admin ❗',
                                   reply_markup=back_admin_panel_kb, parse_mode = "Markdown")

        except:

            if user_nickname == admin[0]:

                await bot.send_message(chat_id, f'Você já é admin ❗',
                                       reply_markup=back_admin_panel_kb)

            else:

                user_list = [user_nickname, None]

                cursor.execute("INSERT INTO admins VALUES (?, ?) ;", user_list)
                conn.commit()

                cursor.close()

                await bot.send_message(chat_id, f'Usuário *{user_nickname}* agora é admin ✅',
                                       reply_markup=back_admin_panel_kb, parse_mode = 'Markdown')

    else:

        try:

            is_admin = cursor.execute('SELECT nickname FROM admins WHERE nickname = ?', (user_nickname,)).fetchone()[0]

            await bot.send_message(chat_id, f'Usuário @{user_nickname} já é admin ❗',
                                   reply_markup=back_admin_panel_kb)

        except:

            creator_id = cursor.execute('SELECT user_id FROM users WHERE nickname = ?', (user_nickname,)).fetchone()[0]

            if creator_id == admin[0]:

                await bot.send_message(chat_id, f'Você já é admin ❗',
                                       reply_markup=back_admin_panel_kb)

            else:

                user_id = cursor.execute('SELECT user_id FROM users WHERE nickname = ?', (user_nickname,)).fetchone()[0]

                user_list = [user_id, user_nickname]

                cursor.execute("INSERT INTO admins VALUES (?, ?) ;", user_list)
                conn.commit()

                cursor.close()

                await bot.send_message(chat_id, f'Usuário @{user_nickname} agora é admin ✅',
                                       reply_markup=back_admin_panel_kb)

async def delete_admin(chat_id, user_nickname):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    if user_nickname.isnumeric() == True:

        cursor.execute('DELETE FROM admins WHERE user_id = ? and user_id = ?', (user_id, user_nickname,))
        conn.commit()

        cursor.close()

        await bot.send_message(chat_id, f'Usuário *{user_nickname}* não é mais admin ✅',
                               reply_markup=back_admin_panel_kb, parse_mode = 'Markdown')

    else:

        cursor.execute('DELETE FROM admins WHERE nickname = ?', (user_nickname,))
        conn.commit()

        cursor.close()

        await bot.send_message(chat_id, f'Usuário @{user_nickname} não é mais admin ✅',
                               reply_markup = back_admin_panel_kb)

async def withdrawal_reject(chat_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    amount = cursor.execute('SELECT amount FROM forms WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (balance + amount, chat_id,))
    conn.commit()

    cursor.execute('DELETE FROM forms WHERE user_id = ?', (chat_id,))
    conn.commit()

    cursor.close()

    await bot.send_message(chat_id, 'Seu saque foi recusado ❎')

async def withdrawal_accept(chat_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    method = cursor.execute('SELECT method FROM forms WHERE user_id = ?', (chat_id,)).fetchone()[0]
    requisites = cursor.execute('SELECT requisites FROM forms WHERE user_id = ?', (chat_id,)).fetchone()[0]
    amount = cursor.execute('SELECT amount FROM forms WHERE user_id = ?', (chat_id,)).fetchone()[0]

    if method == 'qiwi':

        try:

            async with QiwiWallet(api_access_token = token_qiwi, phone_number = number_qiwi) as wallet:

                await wallet.transfer_money(to_phone_number= '+' + str(requisites), amount = amount)

            cursor.execute('DELETE FROM forms WHERE user_id = ?', (chat_id,))
            conn.commit()

            await bot.send_message(chat_id, 'Seu saque foi aprovado ✅')

            cursor.close()

        except Exception as ex:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            amount = cursor.execute('SELECT amount FROM forms WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (balance + amount, chat_id,))
            conn.commit()

            cursor.execute('DELETE FROM forms WHERE user_id = ?', (chat_id,))
            conn.commit()

            cursor.close()

            await bot.send_message(chat_id, 'Falha ao processar o saque ❎')
            await bot.send_message(admin[0], 'Falha ao processar o saque ❎\n\n' + f'{ex}')

    elif method == 'youmoney':

        try:

            w = YooMoneyAPI(token_youmoney)

            async with w:

                await w.transfer_money(
                    to_account = str(requisites),
                    comment= str(requisites),
                    amount = amount
                )

            cursor.execute('DELETE FROM forms WHERE user_id = ?', (chat_id,))
            conn.commit()

            await bot.send_message(chat_id, 'Seu saque foi aprovado ✅')

            cursor.close()

        except Exception as ex:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            amount = cursor.execute('SELECT amount FROM forms WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (balance + amount, chat_id,))
            conn.commit()

            cursor.execute('DELETE FROM forms WHERE user_id = ?', (chat_id,))
            conn.commit()

            cursor.close()

            await bot.send_message(chat_id, 'Falha ao processar o saque ❎')
            await bot.send_message(admin[0], 'Falha ao processar o saque ❎\n\n' + f'{ex}')

    elif method == 'card':

        try:

            async with QiwiWallet(api_access_token = token_qiwi, phone_number = number_qiwi) as wallet:

                await wallet.transfer_money_to_card(card_number= str(requisites), amount = amount)

            cursor.execute('DELETE FROM forms WHERE user_id = ?', (chat_id,))
            conn.commit()

            await bot.send_message(chat_id, 'Seu saque foi aprovado ✅')

            cursor.close()

        except Exception as ex:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            amount = cursor.execute('SELECT amount FROM forms WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (balance + amount, chat_id,))
            conn.commit()

            cursor.execute('DELETE FROM forms WHERE user_id = ?', (chat_id,))
            conn.commit()

            cursor.close()

            await bot.send_message(chat_id, 'Falha ao processar o saque ❎')
            await bot.send_message(admin[0], 'Falha ao processar o saque ❎\n\n' + f'{ex}')

async def forms_action(chat_id, message, c):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    try:

        a = cursor.execute("SELECT user_id FROM forms").fetchone()[0]

        for i in cursor.execute("SELECT user_id, amount, requisites, method FROM forms").fetchall():
            await bot.answer_callback_query(c.id)

            accept_form = InlineKeyboardButton('✅', callback_data=f'{message.chat.id}:accept')
            reject_form = InlineKeyboardButton('❌', callback_data=f'{message.chat.id}:reject')
            check_form = InlineKeyboardButton('Verificar saldo 🔎', callback_data=f'{message.chat.id}:check')
            form_kb = InlineKeyboardMarkup(row_width=2).add(reject_form, accept_form, check_form)

            await bot.send_message(chat_id, f'Pedido de saque 📋'
                                            f'\n\n Nome: *{i[0]}*'
                                            f'\n\n Carteira: *{i[3]}*'
                                            f'\n\n Dados: *{i[2]}*'
                                            f'\n\n Valor: *{i[1]}* 🪙', reply_markup=form_kb, parse_mode='Markdown')

    except TypeError:

        await c.answer('Nenhum pedido encontrado 🔎')

async def getting_demobalance(chat_id, c):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    given = cursor.execute('SELECT given FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    if given == 0:

        cursor.execute('UPDATE demo SET demobalance = ? WHERE user_id = ?', (500, chat_id,))
        conn.commit()

        cursor.execute('UPDATE demo SET given = ? WHERE user_id = ?', (1, chat_id,))
        conn.commit()

        cursor.close()

        await c.answer('Saldo demo creditado: 500 🪙')

    elif given == 1:

        cursor.close()
        await c.answer('Você já resgatou o saldo demo ❗')


