import sqlite3

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from aiogram.utils.markdown import hide_link

from youmoney import *
from buttons import *
from config import *
from payment import *
from states import *
from adminpanel import *
from games import *

conn = sqlite3.connect('bebra.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id STRING , nickname STRING, balance INTEGER , referals INTEGER, photo_id STRING, text STRING, output INTEGER, referer STRING, referal_level INTEGER)')
conn.commit()

cursor.execute('CREATE TABLE IF NOT EXISTS info (user_id STRING, nickname STRING, bill_id STRING, amount STRING, bet INTEGER, game STRING, referal_profit STRING, ban INTEGER, method STRING, voucher STRING, promo STRING, winning INTEGER)')
conn.commit()

cursor.execute('CREATE TABLE IF NOT EXISTS promocode (promo STRING, usage_max INTEGER, usage_actual INTEGER, percent INTEGER)')
conn.commit()

cursor.execute('CREATE TABLE IF NOT EXISTS voucher (voucher STRING, usage_max INTEGER, usage_actual INTEGER, amount INTEGER)')
conn.commit()

cursor.execute('CREATE TABLE IF NOT EXISTS admins (user_id STRING, nickname STRING)')
conn.commit()

cursor.execute('CREATE TABLE IF NOT EXISTS forms (user_id STRING, amount STRING, requisites STRING, method STRING)')
conn.commit()

cursor.execute('CREATE TABLE IF NOT EXISTS payment_youmoney (user_id STRING, nickname STRING, bill_id STRING, amount STRING)')
conn.commit()

cursor.execute('CREATE TABLE IF NOT EXISTS payment_bitcoin (user_id STRING, nickname STRING, bill_id STRING, amount STRING)')
conn.commit()

cursor.execute('CREATE TABLE IF NOT EXISTS payment_qiwi (user_id STRING, nickname STRING, bill_id STRING, amount STRING)')
conn.commit()

cursor.execute('CREATE TABLE IF NOT EXISTS payment_crystalpay (user_id STRING, nickname STRING, bill_id STRING, amount STRING)')
conn.commit()

cursor.execute('CREATE TABLE IF NOT EXISTS demo (user_id STRING, demobalance INTEGER, given INTEGER, state INTEGER)')
conn.commit()

cursor.execute('CREATE TABLE IF NOT EXISTS jackpot (founder STRING, player1 STRING, player2 STRING, player3 STRING, player4 STRING, player5 STRING, amount INTEGER, players INTEGER)')
conn.commit()

storage = MemoryStorage()
bot = Bot(token=token) if token else None
dp = Dispatcher(bot, storage=storage) if bot else None

@dp.message_handler(commands=['start', 'keyboard'])
async def start_handler(message):

    split = message.text.split()

    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (message.chat.id,))
    cur = cursor.fetchone()

    try:

        ban = cursor.execute('SELECT ban FROM info WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

        if ban == 0:

            await bot.send_message(message.chat.id, 'Bem-vindo 👋', reply_markup = kb)

        else:

            await bot.send_message(message.chat.id, 'Você foi banido 🚫', reply_markup = kb_ban)

    except:

        if len(split) == 2:

            if split[1] == str(message.chat.id):

                if cur is None:

                    await add_user(message.chat.id, message.from_user.username)

                else:

                    await bot.send_message(message.chat.id, 'Bem-vindo 👋', reply_markup=kb)

            else:

                if cur is None:

                    await add_user_with_referal(message.chat.id, split[1], message.from_user.username)

                else:

                    await bot.send_message(message.chat.id, 'Bem-vindo 👋', reply_markup=kb)

        else:

            if cur is None:

                await add_user(message.chat.id, message.from_user.username)

            else:

                await bot.send_message(message.chat.id, 'Bem-vindo 👋', reply_markup=kb)

# Обработчик текста
@dp.message_handler(content_types=['text'])
async def text_handler(message, state: FSMContext):

    chat_id = message.chat.id
    message_id = message.message_id

    msg = message.text

    ban = cursor.execute('SELECT ban FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

    data_good = []
    data_bad = []

    for i in cursor.execute('SELECT promo FROM promocode WHERE usage_actual < usage_max ').fetchall():

        data_good.append(i)

    b = (((((''.join(''.join(str(elems)) for elems in data_good))).replace(',', ' ')).replace('(', '')).replace(')',
                                                                                                                   '')).replace(
        "'", '')

    for i in cursor.execute('SELECT voucher FROM voucher WHERE usage_actual < usage_max ').fetchall():

        data_bad.append(i)

    a = (((((''.join(''.join(str(elems)) for elems in data_bad))).replace(',', ' ')).replace('(', '')).replace(')',
                                                                                                                   '')).replace(
        "'", '')

    a = a.split()
    b = b.split()

    if ban != 1:

        if msg in b:

            await use_promo(chat_id, msg)

        elif msg in a:

            await use_voucher(chat_id, msg)

        else:

            if ban != 1:

                if msg == 'Jogos 🎮':

                    url = 'https://telegra.ph/file/275afc68305449732ffe7.jpg'
                    text = 'Escolha o jogo 🎮'

                    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                    if st == 1:

                        await message.answer(f'Você está no saldo demo 🕹{hide_link(url)}', parse_mode='HTML', reply_markup = games)


                    else:

                        await message.answer(f'{hide_link(url)}', parse_mode='HTML',
                                             reply_markup=games)

                elif msg == 'Perfil 👨‍💻':

                    referals = cursor.execute('SELECT referals FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                    referal_level = cursor.execute('SELECT referal_level FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                    referal_profit = cursor.execute('SELECT referal_profit FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

                    ref_link = 'https://telegram.me/{}?start={}'
                    me = await bot.get_me()
                    username = me.username
                    ref = ref_link.format(username, message.from_user.id)
                    url = 'https://telegra.ph/file/0cec7cc8de99e7f9ee639.jpg'

                    admins = cursor.execute('SELECT user_id FROM admins').fetchall()
                    users = []

                    for i in admins:
                        users.append(i[0])

                    if message.chat.id in users:

                        await bot.send_message(message.chat.id,
                                               f'🤖 Seu ID: <b>{message.from_user.id}</b> \n \n💰 Seu saldo: <b>{balance} 🪙</b>\n \n👥 Indicados: <b>{referals}</b> \n \n🍬 Ganhos com indicação: <b>{referal_profit}</b> | Nível: <b>{referal_level}</b> \n \n🔗 Link de indicação: \n \n <code>{ref}</code> - <b>toque para copiar</b> {hide_link(url)}',
                                               reply_markup=admin_profile, parse_mode="HTML")

                    elif message.chat.id in admin:

                        await bot.send_message(message.chat.id,
                                               f'🤖 Seu ID: <b>{message.from_user.id}</b> \n \n💰 Seu saldo: <b>{balance} 🪙</b>\n \n👥 Indicados: <b>{referals}</b> \n \n🍬 Ganhos com indicação: <b>{referal_profit}</b> | Nível: <b>{referal_level}</b> \n \n🔗 Link de indicação: \n \n <code>{ref}</code> - <b>toque para copiar</b> {hide_link(url)}',
                                               reply_markup=creator_profile, parse_mode="HTML")
                    else:

                        await bot.send_message(chat_id,
                                               f'🤖 Seu ID: <b>{message.from_user.id}</b> \n \n💰 Seu saldo: <b>{balance} 🪙</b>\n \n👥 Indicados: <b>{referals}</b> \n \n🍬 Ganhos com indicação: <b>{referal_profit}</b> | Nível: <b>{referal_level}</b> \n \n🔗 Link de indicação: \n \n <code>{ref}</code> - <b>toque para copiar</b> {hide_link(url)}',
                                               reply_markup=user_profile, parse_mode="HTML")

                elif msg == 'Suporte 🛎':

                    url = 'https://telegra.ph/file/5579c411944bc187d554e.jpg'

                    bt = InlineKeyboardButton('Falar com o suporte 🖊', url =f'tg://resolve?domain={support_name}')

                    keyboard = InlineKeyboardMarkup(row_width=1).add(bt)
                    await message.answer(f'{hide_link(url)}', reply_markup = keyboard, parse_mode='HTML')

                elif msg == 'FAQ 📖':

                    url = 'https://telegra.ph/file/40d978777a2f90b868997.jpg'

                    link = InlineKeyboardButton('Ler 📜', callback_data='rules', url = 'https://telegra.ph/Informaciya-05-21-6')
                    link_kb = InlineKeyboardMarkup(row_width=2).add(link)

                    await message.answer(f'{hide_link(url)}', reply_markup = link_kb, parse_mode='HTML')

                else:

                    await bot.send_message(message.chat.id, "Não reconheço esse comando 🥺")

    else:

        await bot.send_message(chat_id, "Você foi banido 🚫", reply_markup=kb_ban)

@dp.message_handler(state = TestStates.activate_voucher)
async def activate_voucher(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['promo'] = message.text

    data_bad = []

    for i in cursor.execute('SELECT voucher FROM voucher WHERE usage_actual < usage_max ').fetchall():

        data_bad.append(i)

    a = (((((''.join(''.join(str(elems)) for elems in data_bad))).replace(',', ' ')).replace('(', '')).replace(')',
                                                                                                                   '')).replace(
        "'", '')

    a = a.split()

    while True:

        if data['promo'] in a:

            await use_voucher(message.chat.id, message.text)
            await state.finish()
            break

        else:

            await bot.send_message(message.chat.id, 'Voucher não encontrado 🔎', reply_markup = cancel_voucher_kb1)
            break

@dp.message_handler(state = TestStates.activate_promo)
async def activate_voucher(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['promo'] = message.text

    data_bad = []

    for i in cursor.execute('SELECT promo FROM promocode WHERE usage_actual < usage_max ').fetchall():

        data_bad.append(i)

    a = (((((''.join(''.join(str(elems)) for elems in data_bad))).replace(',', ' ')).replace('(', '')).replace(')',
                                                                                                                   '')).replace(
        "'", '')

    a = a.split()

    while True:

        if data['promo'] in a:

            await use_promo(message.chat.id, message.text)
            await state.finish()
            break

        else:

            await bot.send_message(message.chat.id, 'Cupom não encontrado 🔎', reply_markup = cancel_voucher_kb1)
            break

@dp.message_handler(state=TestStates.promo)
async def get_amount(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['promo'] = message.text

    data = data['promo'].split()

    while True:

        try:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            user_list = [data[0], data[1], 0, data[2]]

            cursor.execute("INSERT INTO promocode VALUES (?, ?, ?, ?) ;", user_list)
            conn.commit()

            cursor.close()

            await state.finish()
            await bot.send_message(message.chat.id, f'Cupom *{data[0]}* criado ✅', reply_markup= back_promocode_kb, parse_mode = 'Markdown')
            break

        except Exception as e:

            print(e)
            print(1)
            await bot.send_message(message.chat.id, 'Use o formato ⚠ \n\n *BEBRA777 50 1000*', reply_markup = cancel_promo_kb, parse_mode = 'Markdown')
            break

@dp.message_handler(state=TestStates.delete_promo)
async def get_amount(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['promo'] = message.text

    data = data['promo']

    while True:

        try:

            await delete_promo(message.chat.id, data)
            await state.finish()
            break

        except Exception as e:

            print(e)
            print(2)
            await bot.send_message(message.chat.id, 'Use o formato ⚠ \n\n *BEBRA777*', reply_markup = cancel_promo_kb, parse_mode = 'Markdown')
            break

@dp.message_handler(state=TestStates.voucher)
async def get_amount(message: types.Message, state: FSMContext):


    data = await state.get_data()
    data['promo'] = message.text

    data = data['promo'].split()

    while True:

        try:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            user_list = [data[0], data[1], 0, data[2]]

            cursor.execute("INSERT INTO voucher VALUES (?, ?, ?, ?) ;", user_list)
            conn.commit()

            cursor.close()

            await state.finish()
            await bot.send_message(message.chat.id, f'Voucher *{data[0]}* criado ✅', reply_markup = back_voucher_kb, parse_mode = 'Markdown')
            break

        except:

            await bot.send_message(message.chat.id, 'Use o formato ⚠ \n\n *BEBRA777 50 1000*', reply_markup = cancel_promo_kb, parse_mode = 'Markdown')
            break

@dp.message_handler(state=TestStates.delete_voucher)
async def get_amount(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['promo'] = message.text

    data = data['promo']

    while True:

        try:

            await delete_voucher(message.chat.id, data)
            await state.finish()
            break

        except:

            await bot.send_message(message.chat.id, 'Use o formato ⚠ \n\n *BEBRA777*', parse_mode = 'Markdown')
            break

@dp.message_handler(state=TestStates.qiwi)
async def get_amount(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['amount'] = message.text

    while True:

        try:

            int(data['amount'])

            try:

                if int(data['amount']) != 0:

                    if int(data['amount']) >= 50:

                        await state.finish()
                        await create_payment_qiwi(data['amount'], message.chat.id)
                        break

                    else:

                         await bot.send_message(message.chat.id, 'Depósito mínimo = 50 ⚠', reply_markup = cancel_payment)
                         break
                else:

                    await bot.send_message(message.chat.id, 'O valor precisa ser maior que 0 ⚠', reply_markup = cancel_payment)
                    break

            except Exception as e:

                print(e)
                break

        except ValueError:

            await bot.send_message(message.chat.id, 'Envie só o número, sem símbolos ⚠', reply_markup = cancel_payment)
            break

@dp.message_handler(state=TestStates.youmoney)
async def get_amount(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['amount'] = message.text

    while True:

        try:

            int(data['amount'])

            try:

                if int(data['amount']) != 0:

                    if int(data['amount']) >= 50:

                        await state.finish()
                        await create_payment_youmoney(data['amount'], message.chat.id)
                        break

                    else:

                         await bot.send_message(message.chat.id, 'Depósito mínimo = 50 ⚠', reply_markup = cancel_payment)
                         break

                else:

                    await bot.send_message(message.chat.id, 'O valor precisa ser maior que 0 ⚠', reply_markup = cancel_payment)
                    break

            except Exception as exc:

                print(exc)
                break

        except ValueError:

            await bot.send_message(message.chat.id, 'Envie só o número, sem símbolos ⚠', reply_markup = cancel_payment)
            break

@dp.message_handler(state=TestStates.card)
async def get_amount(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['amount'] = message.text

    while True:

        try:

            int(data['amount'])

            try:

                if int(data['amount']) >= 50:

                    await state.finish()
                    await create_payment_qiwi(data['amount'], message.chat.id)
                    break

                else:

                    await bot.send_message(message.chat.id, 'Depósito mínimo = 50 ⚠',
                                           reply_markup=cancel_payment)
                    break

            except Exception as exc:

                print(exc)
                break

        except ValueError:

            await bot.send_message(message.chat.id, 'Envie só o número, sem símbolos ⚠', reply_markup = cancel_payment)
            break

@dp.message_handler(state=TestStates.bitcoin)
async def get_amount(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['amount'] = message.text

    while True:

        try:

            int(data['amount'])

            try:

                if int(data['amount']) != 0:

                    if int(data['amount']) >= 50:

                        await state.finish()
                        await create_bill_btc(message.chat.id, message.chat.id, data['amount'], data['amount'])
                        break

                    else:

                         await bot.send_message(message.chat.id, 'Depósito mínimo = 50 ⚠', reply_markup = cancel_payment)
                         break

                else:

                    await bot.send_message(message.chat.id, 'O valor precisa ser maior que 0 ⚠', reply_markup = cancel_payment)
                    break

            except Exception as e:
                print(e)
                break

        except ValueError:

            await bot.send_message(message.chat.id, 'Envie só o número, sem símbolos ⚠')
            break

@dp.message_handler(state=TestStates.crystalpay)
async def get_amount(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['amount'] = message.text

    while True:

        try:

            int(data['amount'])

            try:

                if int(data['amount']) != 0:

                    if int(data['amount']) >= 50:

                        await state.finish()
                        await create_payment_crystalpay(data['amount'], message.chat.id)
                        break

                    else:

                         await bot.send_message(message.chat.id, 'Depósito mínimo = 50 ⚠', reply_markup = cancel_payment)
                         break
                else:

                    await bot.send_message(message.chat.id, 'O valor precisa ser maior que 0 ⚠', reply_markup = cancel_payment)
                    break

            except Exception as e:

                print(e)
                break

        except ValueError:

            await bot.send_message(message.chat.id, 'Envie só o número, sem símbolos ⚠', reply_markup = cancel_payment)
            break

@dp.message_handler(state=TestStates.mail)
async def mailing(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['mail'] = message.text

    cursor.execute('UPDATE users SET text = ? WHERE user_id = ?', (data['mail'], message.chat.id,))
    conn.commit()

    await bot.send_message(message.chat.id, 'Envie a foto do envio 🖼')
    await TestStates.photo.set()

@dp.message_handler(content_types=['photo'], state=TestStates.photo)
async def photo_for_mailing(message: types.Message, state: FSMContext):
    await state.finish()

    data = await state.get_data()
    data['photo'] = message.photo[-1].file_id

    cursor.execute('UPDATE users SET photo_id = ? WHERE user_id = ?', (data['photo'], message.chat.id,))
    conn.commit()

    photo = cursor.execute('SELECT photo_id FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
    text = cursor.execute('SELECT text FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

    await bot.send_message(message.chat.id, 'Confirme a mensagem do envio ⬇')
    await bot.send_photo(chat_id = message.chat.id, photo=photo, caption=text, parse_mode='Markdown', reply_markup=confirm)

@dp.message_handler(state=TestStates.user_ban)
async def ban_user(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['ban_user'] = message.text

    while True:

        if '@' in data['ban_user']:

            users = []

            for i in cursor.execute('SELECT nickname FROM info').fetchall():

                users.append('@' + i[0])

            if data['ban_user'] in users:

                await state.finish()
                await ban_user_action(message.chat.id, bot, data['ban_user'].replace('@', ''))
                break

            else:

                await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠' ,reply_markup = cancel_user_kb)
                break

        elif data['ban_user'].isnumeric() == True:

            users = []

            for i in cursor.execute('SELECT user_id FROM info').fetchall():

                users.append(i[0])

            if int(data['ban_user']) in users:

                await state.finish()
                await ban_user_action(message.chat.id, bot, data['ban_user'])
                break

            else:

                await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠' ,reply_markup = cancel_user_kb)

            break

        else:
            print(type(data['ban_user']))
            await bot.send_message(message.chat.id, 'Envie @usuario ou o ID ⚠',
                                   reply_markup=cancel_user_kb)
            break

@dp.message_handler(state=TestStates.user_unban)
async def mailing(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['ban_user'] = message.text

    while True:

        if '@' in data['ban_user']:

            users = []

            for i in cursor.execute('SELECT nickname FROM info').fetchall():

                users.append('@' + i[0])

            if data['ban_user'] in users:

                await state.finish()
                await ban_user_action(message.chat.id, bot, data['ban_user'].replace('@', ''))
                break

            else:

                await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠' ,reply_markup = cancel_user_kb)
                break

        elif data['ban_user'].isnumeric() == True:

            users = []

            for i in cursor.execute('SELECT user_id FROM info').fetchall():

                users.append(i[0])

            if int(data['ban_user']) in users:

                await state.finish()
                await unban_user_action(message.chat.id, bot, data['ban_user'])
                break

            else:

                await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠' ,reply_markup = cancel_user_kb)

            break

        else:
            print(type(data['ban_user']))
            await bot.send_message(message.chat.id, 'Envie @usuario ou o ID ⚠',
                                   reply_markup=cancel_user_kb)
            break


@dp.message_handler(state=TestStates.user_increase_balance)
async def increase(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['user'] = message.text

    while True:

        if len(data['user'].split(' ')) == 2:

            ides = []
            nicknames = []

            for i in cursor.execute('SELECT user_id FROM users').fetchall():

                ides.append(str(i[0]))

            for i in cursor.execute('SELECT nickname FROM users').fetchall():

                nicknames.append(i[0])

            if data['user'].split(' ')[0].replace('@', '') in nicknames:

                await state.finish()
                await user_increase_balance(message.chat.id, ((data['user'].split(' ')[0])).replace('@', ''),
                                            data['user'].split(' ')[1])
                break

            elif data['user'].split(' ')[0] in ides:

                await state.finish()
                await user_increase_balance(message.chat.id, data['user'].split(' ')[0], data['user'].split(' ')[1])
                break

            else:

                await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠', reply_markup=cancel_user_kb)
                break

        else:

            await bot.send_message(message.chat.id, 'Formato inválido ⚠', reply_markup=cancel_user_kb)
            break

@dp.message_handler(state=TestStates.user_decrease_balance)
async def decrease(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['user'] = message.text

    while True:

        if len(data['user'].split(' ')) == 2:

            ides = []
            nicknames = []

            for i in cursor.execute('SELECT user_id FROM users').fetchall():

                ides.append(str(i[0]))

            for i in cursor.execute('SELECT nickname FROM users').fetchall():

                nicknames.append(i[0])

            if data['user'].split(' ')[0].replace('@', '') in nicknames:

                await state.finish()
                await user_decrease_balance(message.chat.id, ((data['user'].split(' ')[0])).replace('@', ''),
                                            data['user'].split(' ')[1])
                break

            elif data['user'].split(' ')[0] in ides:

                await state.finish()
                await user_decrease_balance(message.chat.id, data['user'].split(' ')[0], data['user'].split(' ')[1])
                break

            else:

                await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠', reply_markup=cancel_user_kb)
                break

        else:

            await bot.send_message(message.chat.id, 'Formato inválido ⚠', reply_markup=cancel_user_kb)
            break


@dp.message_handler(state=TestStates.add_admin)
async def add_admin_action(message: types.Message, state: FSMContext):


    data = await state.get_data()
    data['user'] = message.text

    while True:

        user = data['user']

        if user.isnumeric() == True:

            users = []

            for i in cursor.execute('SELECT user_id FROM info').fetchall():
                users.append(i[0])

            if int(data['user']) in users:

                user_nickname = cursor.execute('SELECT nickname FROM users WHERE user_id = ?', (data['user'],)).fetchone()[0]

                if user_nickname is None:

                    await state.finish()
                    await add_admin(message.chat.id, data['user'])
                    break

                else:

                    await state.finish()
                    await add_admin(message.chat.id, user_nickname)
                    break

            else:

                await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠', reply_markup=cancel_admin_kb)
                break

        else:

            if '@' in data['user']:

                try:

                    a = cursor.execute('SELECT nickname FROM users WHERE nickname = ?', (data['user'].replace('@', ''),)).fetchone()[0]

                    if a != None:

                        if data['user'].replace('@', '') == a:

                            await state.finish()
                            await add_admin(message.chat.id, data['user'].replace('@', ''))
                            break

                        else:

                            await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠',
                                                   reply_markup=cancel_user_kb)
                            break

                    elif a == None:

                        await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠',
                                               reply_markup=cancel_admin_kb)
                        break

                except Exception as e:

                    await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠', reply_markup=cancel_admin_kb)
                    break

            else:

                print(1)
                break

@dp.message_handler(state=TestStates.delete_admin)
async def delete_admin_action(message: types.Message, state: FSMContext):
    data = await state.get_data()
    data['user'] = message.text

    while True:

        user = data['user']

        if user.isnumeric() == True:

            users = []

            for i in cursor.execute('SELECT user_id FROM info').fetchall():
                users.append(i[0])

            if int(data['user']) in users:

                user_nickname = \
                cursor.execute('SELECT nickname FROM users WHERE user_id = ?', (data['user'],)).fetchone()[0]

                if user_nickname is None:

                    await state.finish()
                    await delete_admin(message.chat.id, data['user'])
                    break

                else:

                    await state.finish()
                    await delete_admin(message.chat.id, user_nickname)
                    break

            else:

                await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠', reply_markup=cancel_admin_kb)
                break

        else:

            if '@' in data['user']:

                try:

                    a = cursor.execute('SELECT nickname FROM users WHERE nickname = ?',
                                       (data['user'].replace('@', ''),)).fetchone()[0]

                    if a != None:

                        if data['user'].replace('@', '') == a:

                            await state.finish()
                            await delete_admin(message.chat.id, data['user'].replace('@', ''))
                            break

                        else:

                            await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠',
                                                   reply_markup=cancel_user_kb)
                            break

                    elif a == None:

                        await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠',
                                               reply_markup=cancel_user_kb)
                        break

                except Exception as e:

                    print(e)
                    await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠',
                                           reply_markup=cancel_user_kb)
                    break

            else:

                await bot.send_message(message.chat.id, 'Usuário não encontrado ⚠',
                                       reply_markup=cancel_user_kb)
                break

@dp.message_handler(state=TestStates.amount)
async def amount(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['user'] = message.text

    while True:

        if data['user'].isnumeric() == True:

            if int(data['user']) >= 50:

                if data['user'].isnumeric() == False:
                    print(data['user'].isnumeric())
                    await bot.send_message(message.chat.id, 'Envie só o número, sem símbolos ⚠')
                    break

                else:

                    conn = sqlite3.connect('bebra.db', check_same_thread=False)
                    cursor = conn.cursor()

                    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                    cursor.close()

                    if int(data['user']) <= balance:

                        await state.finish()

                        conn = sqlite3.connect('bebra.db', check_same_thread=False)
                        cursor = conn.cursor()

                        method = cursor.execute('SELECT method FROM info WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                        balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                        user_list = [message.chat.id, data['user'], None, method]

                        cursor.execute("INSERT INTO forms VALUES (?, ?, ?, ?) ;", user_list)
                        conn.commit()

                        cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (balance - int(data['user']), message.chat.id, ))
                        conn.commit()

                        cursor.close()

                        await bot.send_message(message.chat.id, 'Envie o telefone ou o cartão 📮')
                        await TestStates.requisites.set()

                        break

                    else:

                        await bot.send_message(message.chat.id, 'O valor não pode ser maior que o saldo ⚠')
                        break

            else:

                await bot.send_message(message.chat.id, 'Saque mínimo = 150 ⚠')
                break

        else:

            await bot.send_message(message.chat.id, 'Envie só o número, sem símbolos ⚠')
            break

@dp.message_handler(state=TestStates.requisites)
async def requisites(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['user'] = message.text

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    method = cursor.execute('SELECT method FROM forms WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

    cursor.close()

    while True:

        if method == 'qiwi':

            if len(data['user']) == 12:

                if '+' in data['user']:

                    await state.finish()

                    conn = sqlite3.connect('bebra.db', check_same_thread=False)
                    cursor = conn.cursor()

                    cursor.execute('UPDATE forms SET requisites = ? WHERE user_id = ?', (data['user'], message.chat.id,))
                    conn.commit()

                    requisites = cursor.execute('SELECT requisites FROM forms WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                    amount = cursor.execute('SELECT amount FROM forms WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                    nickname = cursor.execute('SELECT nickname FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                    method = cursor.execute('SELECT method FROM forms WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                    accept_form = InlineKeyboardButton('✅', callback_data=f'{message.chat.id}:accept')
                    reject_form = InlineKeyboardButton('❌', callback_data=f'{message.chat.id}:reject')
                    check_form = InlineKeyboardButton('Verificar saldo 🔎', callback_data=f'{message.chat.id}:check')
                    form_kb = InlineKeyboardMarkup(row_width=2).add(reject_form, accept_form, check_form)

                    await bot.send_message(message.chat.id, 'Pedido em análise 🔄', reply_markup = back_menu_kb)

                    output = cursor.execute('SELECT output FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                    cursor.close()

                    if output == 0:

                        await bot.send_message(admin[0], f'Novo pedido de saque 🔔', parse_mode='Markdown')
                        break

                    elif output == 1:

                        await withdrawal_accept(message.chat.id)
                        break

                else:

                    await bot.send_message(message.chat.id, 'Formato de telefone/cartão inválido ⚠', parse_mode = 'Markdown')
                    break

            else:

                await bot.send_message(message.chat.id, 'Formato de telefone/cartão inválido ⚠', parse_mode = 'Markdown')
                break

        elif method == 'youmoney':

            if len(data['user']) == 16:

                await state.finish()

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                cursor.execute('UPDATE forms SET requisites = ? WHERE user_id = ?', (data['user'], message.chat.id,))
                conn.commit()

                requisites = cursor.execute('SELECT requisites FROM forms WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                amount = cursor.execute('SELECT amount FROM forms WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                nickname = cursor.execute('SELECT nickname FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                method = cursor.execute('SELECT method FROM forms WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                accept_form = InlineKeyboardButton('✅', callback_data=f'{message.chat.id}:accept')
                reject_form = InlineKeyboardButton('❌', callback_data=f'{message.chat.id}:reject')
                check_form = InlineKeyboardButton('Verificar saldo 🔎', callback_data=f'{message.chat.id}:check')
                form_kb = InlineKeyboardMarkup(row_width=2).add(reject_form, accept_form, check_form)

                await bot.send_message(message.chat.id, 'Pedido em análise 🔄', reply_markup=back_menu_kb)

                output = cursor.execute('SELECT output FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                cursor.close()

                if output == 0:

                    await bot.send_message(admin[0], f'Novo pedido de saque 🔔', parse_mode='Markdown')
                    break

                elif output == 1:

                    await withdrawal_accept(message.chat.id)

                break

            else:

                await bot.send_message(message.chat.id, 'Formato de telefone/cartão inválido ⚠', parse_mode = 'Markdown')
                break

        elif method == 'card':

            if len(data['user']) == 16:

                await state.finish()

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                cursor.execute('UPDATE forms SET requisites = ? WHERE user_id = ?', (data['user'], message.chat.id,))
                conn.commit()

                requisites = cursor.execute('SELECT requisites FROM forms WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                amount = cursor.execute('SELECT amount FROM forms WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                nickname = cursor.execute('SELECT nickname FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                method = cursor.execute('SELECT method FROM forms WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                accept_form = InlineKeyboardButton('✅', callback_data=f'{message.chat.id}:accept')
                reject_form = InlineKeyboardButton('❌', callback_data=f'{message.chat.id}:reject')
                check_form = InlineKeyboardButton('Verificar saldo 🔎', callback_data=f'{message.chat.id}:check')
                form_kb = InlineKeyboardMarkup(row_width=2).add(reject_form, accept_form, check_form)
                await bot.send_message(message.chat.id, 'Pedido em análise 🔄', reply_markup=back_menu_kb)

                output = cursor.execute('SELECT output FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                cursor.close()

                if output == 0:

                    await bot.send_message(admin[0], f'Novo pedido de saque 🔔', parse_mode='Markdown')
                    break

                elif output == 1:

                    await withdrawal_accept(message.chat.id)
                    break

            else:

                await bot.send_message(message.chat.id, 'Formato de telefone/cartão inválido ⚠', parse_mode = 'Markdown')
                break

        else:

            await bot.send_message(message.chat.id, 'O saque só pode ser feito via *QIWI*, *YooMoney* ou *cartão* ⚠', parse_mode='Markdown')
            break

@dp.message_handler(state=TestStates.requisites_v1)
async def requisites_v1(message: types.Message, state: FSMContext):

    data = await state.get_data()
    data['user'] = message.text

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    method = cursor.execute('SELECT method FROM info WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

    while True:

        if method == 'qiwi':

            if len(data['user']) == 12:

                if '+' in str(data['user']):

                    await state.finish()

                    conn = sqlite3.connect('bebra.db', check_same_thread=False)
                    cursor = conn.cursor()

                    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                    method = cursor.execute('SELECT method FROM info WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                    nickname = cursor.execute('SELECT nickname FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                    user_list = [message.chat.id, balance, data['user'], method]

                    cursor.execute("INSERT INTO forms VALUES (?, ?, ?, ?) ;", user_list)
                    conn.commit()

                    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (0, message.chat.id,))
                    conn.commit()

                    requisites = cursor.execute('SELECT requisites FROM forms WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                    accept_form = InlineKeyboardButton('✅', callback_data=f'{message.chat.id}:accept')
                    reject_form = InlineKeyboardButton('❌', callback_data=f'{message.chat.id}:reject')
                    check_form = InlineKeyboardButton('Verificar saldo 🔎', callback_data=f'{message.chat.id}:check')
                    form_kb = InlineKeyboardMarkup(row_width=2).add(reject_form, accept_form, check_form)

                    await bot.send_message(message.chat.id, 'Pedido em análise 🔄', reply_markup=back_menu_kb)

                    output = cursor.execute('SELECT output FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                    cursor.close()

                    if output == 0:

                        await bot.send_message(admin[0], f'Novo pedido de saque 🔔', parse_mode='Markdown')
                        break

                    elif output == 1:

                        await withdrawal_accept(message.chat.id)
                        break

                else:

                    await bot.send_message(message.chat.id, 'Formato de número inválido ⚠', parse_mode = 'Markdown')
                    break

            else:

                await bot.send_message(message.chat.id, 'Formato de número inválido ⚠', parse_mode='Markdown')
                break

        elif method == 'card':

            if len(data['user']) == 16:

                await state.finish()

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                method = cursor.execute('SELECT method FROM info WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                nickname = cursor.execute('SELECT nickname FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                user_list = [message.chat.id, balance, data['user'], method]

                cursor.execute("INSERT INTO forms VALUES (?, ?, ?, ?) ;", user_list)
                conn.commit()

                cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (0, message.chat.id,))
                conn.commit()

                requisites = cursor.execute('SELECT requisites FROM forms WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                accept_form = InlineKeyboardButton('✅', callback_data=f'{message.chat.id}:accept')
                reject_form = InlineKeyboardButton('❌', callback_data=f'{message.chat.id}:reject')
                check_form = InlineKeyboardButton('Verificar saldo 🔎', callback_data=f'{message.chat.id}:check')
                form_kb = InlineKeyboardMarkup(row_width=2).add(reject_form, accept_form, check_form)

                await bot.send_message(message.chat.id, 'Pedido em análise 🔄', reply_markup=back_menu_kb)

                output = cursor.execute('SELECT output FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                cursor.close()

                if output == 0:

                    await bot.send_message(admin[0], f'Novo pedido de saque 🔔', parse_mode='Markdown')
                    break

                elif output == 1:

                    await withdrawal_accept(message.chat.id)
                    break

            else:

                await bot.send_message(message.chat.id, 'Formato de cartão inválido ⚠', parse_mode = 'Markdown')
                break

        elif method == 'youmoney':

            if len(data['user']) == 16:

                await state.finish()

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                method = cursor.execute('SELECT method FROM info WHERE user_id = ?', (message.chat.id,)).fetchone()[0]
                nickname = cursor.execute('SELECT nickname FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                user_list = [message.chat.id, balance, data['user'], method]

                cursor.execute("INSERT INTO forms VALUES (?, ?, ?, ?) ;", user_list)
                conn.commit()

                cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (0, message.chat.id,))
                conn.commit()

                requisites = cursor.execute('SELECT requisites FROM forms WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                accept_form = InlineKeyboardButton('✅', callback_data=f'{message.chat.id}:accept')
                reject_form = InlineKeyboardButton('❌', callback_data=f'{message.chat.id}:reject')
                check_form = InlineKeyboardButton('Verificar saldo 🔎', callback_data=f'{message.chat.id}:check')
                form_kb = InlineKeyboardMarkup(row_width=2).add(reject_form, accept_form, check_form)

                await bot.send_message(message.chat.id, 'Pedido em análise 🔄', reply_markup=back_menu_kb)

                output = cursor.execute('SELECT output FROM users WHERE user_id = ?', (message.chat.id,)).fetchone()[0]

                cursor.close()

                if output == 0:

                    await bot.send_message(admin[0], f'Novo pedido de saque 🔔', parse_mode='Markdown')
                    break

                elif output == 1:

                    await withdrawal_accept(message.chat.id)
                    break

            else:

                await bot.send_message(message.chat.id, 'Formato de cartão inválido ⚠', parse_mode = 'Markdown')
                break

        else:

            await bot.send_message(message.chat.id, 'O saque só pode ser feito via *QIWI*, *YooMoney* ou *cartão* ⚠', parse_mode='Markdown')
            break

@dp.callback_query_handler(state = '*')
async def process_callback(c: types.CallbackQuery, state: FSMContext):

    chat_id = c.message.chat.id
    message_id = c.message.message_id
    username = c.from_user.username

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    ban = cursor.execute('SELECT ban FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

    if ban != 1:

        if c.data == 'bet_increase':

            await bot.answer_callback_query(c.id)

            game = cursor.execute('SELECT game FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

            await do_bet_increase(game, chat_id, message_id)

        elif c.data == 'bet_decrease':

            game = cursor.execute('SELECT game FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

            await do_bet_decrease(game, c, chat_id, message_id)

        elif c.data == "roulette":

            cursor.execute('UPDATE info SET game = ? WHERE user_id = ?', (c.data, chat_id,))
            conn.commit()

            game = cursor.execute('SELECT game FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if balance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Deposite ou ative o saldo demo ⚠')
                    await bot.send_message(chat_id, 'O saldo demo está em "Saldo"')

            elif st == 1:

                if demobalance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Saldo demo esgotado ⚠')

        elif c.data == "slots":

            cursor.execute('UPDATE info SET game = ? WHERE user_id = ?', (c.data, chat_id,))
            conn.commit()

            game = cursor.execute('SELECT game FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if balance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Deposite ou ative o saldo demo ⚠')
                    await bot.send_message(chat_id, 'O saldo demo está em "Saldo"')

            elif st == 1:

                if demobalance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Saldo demo esgotado ⚠')

        elif c.data == "bowling":

            cursor.execute('UPDATE info SET game = ? WHERE user_id = ?', (c.data, chat_id,))
            conn.commit()

            game = cursor.execute('SELECT game FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if balance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Deposite ou ative o saldo demo ⚠')
                    await bot.send_message(chat_id, 'O saldo demo está em "Saldo"')

            elif st == 1:

                if demobalance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Saldo demo esgotado ⚠')


        elif c.data == "darts":

            cursor.execute('UPDATE info SET game = ? WHERE user_id = ?', (c.data, chat_id,))
            conn.commit()

            game = cursor.execute('SELECT game FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if balance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Deposite ou ative o saldo demo ⚠')
                    await bot.send_message(chat_id, 'O saldo demo está em "Saldo"')

            elif st == 1:

                if demobalance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Saldo demo esgotado ⚠')

        elif c.data == "shell":

            cursor.execute('UPDATE info SET game = ? WHERE user_id = ?', (c.data, chat_id,))
            conn.commit()

            game = cursor.execute('SELECT game FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if balance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Deposite ou ative o saldo demo ⚠')
                    await bot.send_message(chat_id, 'O saldo demo está em "Saldo"')

            elif st == 1:

                if demobalance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Saldo demo esgotado ⚠')

        elif c.data == 'shell_first':

            await bot.answer_callback_query(c.id)
            await shell_first(c, chat_id, message_id)

        elif c.data == 'shell_second':

            await bot.answer_callback_query(c.id)
            await shell_second(c, chat_id, message_id)

        elif c.data == 'shell_third':

            await bot.answer_callback_query(c.id)
            await shell_third(c, chat_id, message_id)

        elif c.data == "basketball":

            cursor.execute('UPDATE info SET game = ? WHERE user_id = ?', (c.data, chat_id,))
            conn.commit()

            game = cursor.execute('SELECT game FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if balance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Deposite ou ative o saldo demo ⚠')
                    await bot.send_message(chat_id, 'O saldo demo está em "Saldo"')

            elif st == 1:

                if demobalance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Saldo demo esgotado ⚠')

        elif c.data == "football":

            cursor.execute('UPDATE info SET game = ? WHERE user_id = ?', (c.data, chat_id,))
            conn.commit()

            game = cursor.execute('SELECT game FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if balance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Deposite ou ative o saldo demo ⚠')
                    await bot.send_message(chat_id, 'O saldo demo está em "Saldo"')

            elif st == 1:

                if demobalance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Saldo demo esgotado ⚠')

        elif c.data == "dice":

            cursor.execute('UPDATE info SET game = ? WHERE user_id = ?', (c.data, chat_id,))
            conn.commit()

            game = cursor.execute('SELECT game FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if balance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Deposite ou ative o saldo demo ⚠')
                    await bot.send_message(chat_id, 'O saldo demo está em "Saldo"')

            elif st == 1:

                if demobalance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Saldo demo esgotado ⚠')

        elif c.data == "coin":

            cursor.execute('UPDATE info SET game = ? WHERE user_id = ?', (c.data, chat_id,))
            conn.commit()

            game = cursor.execute('SELECT game FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if balance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Deposite ou ative o saldo demo ⚠')
                    await bot.send_message(chat_id, 'O saldo demo está em "Saldo"')

            elif st == 1:

                if demobalance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Saldo demo esgotado ⚠')

        elif c.data == 'jackpot':

            cursor.execute('UPDATE info SET game = ? WHERE user_id = ?', (c.data, chat_id,))
            conn.commit()

            game = cursor.execute('SELECT game FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if balance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Deposite ou ative o saldo demo ⚠')
                    await bot.send_message(chat_id, 'O saldo demo está em "Saldo"')

            elif st == 1:

                if demobalance != 0:

                    await bot.answer_callback_query(c.id)
                    await do_bet(game, chat_id, message_id)

                else:

                    await c.answer('Saldo demo esgotado ⚠')

        elif c.data == 'bet_confirm_roulette' or c.data == 'repeat_roulette':

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if bet >= 25:

                    if balance > 0:

                        if balance >= 25:

                            if balance >= bet:

                                await bot.answer_callback_query(c.id)
                                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                            text='Escolha a aposta ⬇', reply_markup=roulette_kb)

                            else:

                                await bot.answer_callback_query(c.id)
                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await bot.answer_callback_query(c.id)
                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await bot.answer_callback_query(c.id)
                        await c.answer('Deposite para continuar ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

            elif st == 1:

                if bet >= 25:

                    if demobalance > 0:

                        if demobalance >= 25:

                            if demobalance >= bet:

                                await bot.answer_callback_query(c.id)
                                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                            text='Escolha a aposta ⬇', reply_markup=roulette_kb)

                            else:

                                await bot.answer_callback_query(c.id)
                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await bot.answer_callback_query(c.id)
                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await bot.answer_callback_query(c.id)
                        await c.answer('Saldo demo esgotado ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

        elif c.data == 'bet_confirm_slots' or c.data == 'repeat_slots':

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if bet >= 25:

                    if balance > 0:

                        if balance >= 25:

                            if balance >= bet:

                                await slots(c, chat_id)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Deposite para continuar ⚠')

                else:

                    await c.answer('Aposta mínima = 25 ⚠')

            elif st == 1:

                if bet >= 25:

                    if demobalance > 0:

                        if demobalance >= 25:

                            if demobalance >= bet:

                                await slots(c, chat_id)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Saldo demo esgotado ⚠')

                else:

                    await c.answer('Aposta mínima = 25 ⚠')

        elif c.data == 'bet_confirm_coin' or c.data == 'repeat_coin':

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if bet >= 25:

                    if balance > 0:

                        if balance >= 25:

                            if balance >= bet:

                                await bot.send_message(chat_id, 'Escolha o lado da moeda ⬇', reply_markup=coin_kb)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Deposite para continuar ⚠')

                else:

                    await c.answer('Aposta mínima = 25 ⚠')

            elif st == 1:

                if bet >= 25:

                    if demobalance > 0:

                        if demobalance >= 25:

                            if demobalance >= bet:

                                await bot.send_message(chat_id, 'Escolha o lado da moeda ⬇', reply_markup = coin_kb)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Saldo demo esgotado ⚠')

                else:

                    await c.answer('Aposta mínima = 25 ⚠')

        elif c.data == 'coin_eagle':

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if bet >= 25:

                    if balance > 0:

                        if balance >= 25:

                            if balance >= bet:

                                await bot.delete_message(chat_id, message_id)
                                await bot.answer_callback_query(c.id)
                                await coin_eagle(chat_id, message_id, c)
                                cursor.close()

                            else:

                                await bot.answer_callback_query(c.id)
                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await bot.answer_callback_query(c.id)
                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await bot.answer_callback_query(c.id)
                        await c.answer('Deposite para continuar ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

            elif st == 1:

                if bet >= 25:

                    if demobalance > 0:

                        if demobalance >= 25:

                            if demobalance >= bet:

                                await bot.delete_message(chat_id, message_id)
                                await bot.answer_callback_query(c.id)
                                await coin_eagle(chat_id, message_id, c)

                            else:

                                await bot.answer_callback_query(c.id)
                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await bot.answer_callback_query(c.id)
                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await bot.answer_callback_query(c.id)
                        await c.answer('Saldo demo esgotado ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

        elif c.data == 'coin_tail':

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if bet >= 25:

                    if balance > 0:

                        if balance >= 25:

                            if balance >= bet:

                                await bot.delete_message(chat_id, message_id)
                                await bot.answer_callback_query(c.id)
                                await coin_eagle(chat_id, message_id, c)

                            else:

                                await bot.answer_callback_query(c.id)
                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await bot.answer_callback_query(c.id)
                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await bot.answer_callback_query(c.id)
                        await c.answer('Deposite para continuar ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

            elif st == 1:

                if bet >= 25:

                    if demobalance > 0:

                        if demobalance >= 25:

                            if demobalance >= bet:

                                await bot.delete_message(chat_id, message_id)
                                await bot.answer_callback_query(c.id)
                                await coin_tail(chat_id, message_id, c)

                            else:

                                await bot.answer_callback_query(c.id)
                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await bot.answer_callback_query(c.id)
                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await bot.answer_callback_query(c.id)
                        await c.answer('Saldo demo esgotado ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

        elif c.data == 'bet_confirm_bowling' or c.data == 'repeat_bowling':

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if bet >= 25:

                    if balance > 0:

                        if balance >= 25:

                            if balance >= bet:

                                await bowling(c, chat_id)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Deposite para continuar ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

            elif st == 1:

                if bet >= 25:

                    if demobalance > 0:

                        if demobalance >= 25:

                            if demobalance >= bet:

                                await bowling(c, chat_id)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Saldo demo esgotado ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

        elif c.data == 'bet_confirm_basketball' or c.data == 'repeat_basketball':

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if bet >= 25:

                    if balance > 0:

                        if balance >= 25:

                            if balance >= bet:

                                await basketball(c, chat_id)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Deposite para continuar ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

            elif st == 1:

                if bet >= 25:

                    if demobalance > 0:

                        if demobalance >= 25:

                            if demobalance >= bet:

                                await basketball(c, chat_id)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Saldo demo esgotado ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

        elif c.data == 'bet_confirm_football' or c.data == 'repeat_football':


            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if bet >= 25:

                    if balance > 0:

                        if balance >= 25:

                            if balance >= bet:

                                await football(c, chat_id)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Deposite para continuar ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

            elif st == 1:

                if bet >= 25:

                    if demobalance > 0:

                        if demobalance >= 25:

                            if demobalance >= bet:

                                await football(c, chat_id)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Saldo demo esgotado ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

        elif c.data == 'bet_confirm_shell' or c.data == 'repeat_shell':

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if bet >= 25:

                    if balance > 0:

                        if balance >= 25:

                            if balance >= bet:

                                await bot.answer_callback_query(c.id)
                                await shell(chat_id, message_id, c)

                            else:

                                await bot.answer_callback_query(c.id)
                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await bot.answer_callback_query(c.id)
                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await bot.answer_callback_query(c.id)
                        await c.answer('Deposite para continuar ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

            elif st == 1:

                if bet >= 25:

                    if demobalance > 0:

                        if demobalance >= 25:

                            if demobalance >= bet:

                                await bot.answer_callback_query(c.id)
                                await shell(chat_id, message_id, c)

                            else:

                                await bot.answer_callback_query(c.id)
                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await bot.answer_callback_query(c.id)
                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await bot.answer_callback_query(c.id)
                        await c.answer('Saldo demo esgotado ⚠')

                else:

                    await bot.answer_callback_query(c.id)
                    await c.answer('Aposta mínima = 25 ⚠')

        elif c.data == 'bet_confirm_dice' or c.data == 'repeat_dice':

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if st == 0:

                if bet >= 25:

                    if balance > 0:

                        if balance >= 25:

                            if balance >= bet:

                                await dice(c, chat_id)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Deposite para continuar ⚠')

                else:

                    await c.answer('Aposta mínima = 25 ⚠')

            elif st == 1:

                if bet >= 25:

                    if demobalance > 0:

                        if demobalance >= 25:

                            if demobalance >= bet:

                                await dice(c, chat_id)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Saldo demo esgotado ⚠')

                else:

                    await c.answer('Aposta mínima = 25 ⚠')

        elif c.data == 'bet_confirm_darts' or c.data == 'repeat_darts':

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            await bot.answer_callback_query(c.id)

            if st == 0:

                if bet >= 25:

                    if balance > 0:

                        if balance >= 25:

                            if balance >= bet:

                                await darts(c, chat_id)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Deposite para continuar ⚠')

                else:

                    await c.answer('Aposta mínima = 25 ⚠')

            elif st == 1:

                if bet >= 25:

                    if demobalance > 0:

                        if demobalance >= 25:

                            if demobalance >= bet:

                                await darts(c, chat_id)

                            else:

                                await c.answer('Deposite ou diminua a aposta ⚠')

                        else:

                            await c.answer('Deposite para continuar ⚠')

                    else:

                        await c.answer('Saldo demo esgotado ⚠')

                else:

                    await c.answer('Aposta mínima = 25 ⚠')

        elif c.data == 'back_profile':

            referals = cursor.execute('SELECT referals FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            referal_level = cursor.execute('SELECT referal_level FROM users WHERE user_id = ?', (chat_id,)).fetchone()[
                0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            referal_profit = cursor.execute('SELECT referal_profit FROM info WHERE user_id = ?', (chat_id,)).fetchone()[
                0]

            ref_link = 'https://telegram.me/{}?start={}'
            me = await bot.get_me()
            username = me.username
            ref = ref_link.format(username, chat_id)
            url = 'https://telegra.ph/file/0cec7cc8de99e7f9ee639.jpg'

            await bot.answer_callback_query(c.id)

            admins = cursor.execute('SELECT user_id FROM admins').fetchall()
            users = []

            for i in admins:

                users.append(i[0])

            if chat_id in admin:

                await bot.edit_message_text(chat_id = chat_id, message_id = message_id, text =
                                       f'🤖 Seu ID: <b>{chat_id}</b> \n \n💰 Seu saldo: <b>{balance} 🪙</b>\n \n👥 Indicados: <b>{referals}</b> \n \n🍬 Ganhos com indicação: <b>{referal_profit}</b> | Nível: <b>{referal_level}</b> \n \n🔗 Link de indicação: \n \n <code>{ref}</code> - <b>toque para copiar</b> {hide_link(url)}',
                                       reply_markup= creator_profile, parse_mode="HTML")


            elif chat_id in users:

                await bot.edit_message_text(chat_id = chat_id, message_id = message_id, text =
                                       f'🤖 Seu ID: <b>{chat_id}</b> \n \n💰 Seu saldo: <b>{balance} 🪙</b>\n \n👥 Indicados: <b>{referals}</b> \n \n🍬 Ganhos com indicação: <b>{referal_profit}</b> | Nível: <b>{referal_level}</b> \n \n🔗 Link de indicação: \n \n <code>{ref}</code> - <b>toque para copiar</b> {hide_link(url)}',
                                       reply_markup =admin_profile, parse_mode="HTML")

            else:

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=
                f'🤖 Seu ID: <b>{chat_id}</b> \n \n💰 Seu saldo: <b>{balance} 🪙</b>\n \n👥 Indicados: <b>{referals}</b> \n \n🍬 Ganhos com indicação: <b>{referal_profit}</b> | Nível: <b>{referal_level}</b> \n \n🔗 Link de indicação: \n \n <code>{ref}</code> - <b>toque para copiar</b> {hide_link(url)}',
                                            reply_markup= user_profile, parse_mode="HTML")

        elif c.data == 'back_menu':

            url = 'https://telegra.ph/file/275afc68305449732ffe7.jpg'
            text = 'Escolha o jogo 🎮'

            await bot.answer_callback_query(c.id)
            await bot.edit_message_text(chat_id = chat_id, message_id=message_id, text=f'{hide_link(url)}',
                                            parse_mode='HTML', reply_markup = games)

        elif c.data == 'back_users':

            await bot.answer_callback_query(c.id)
            await users_actions(chat_id, message_id, bot)

        elif c.data == 'deposit':

            await bot.answer_callback_query(c.id)
            url = 'https://telegra.ph/file/75c7432e1c5b8964d257e.jpg'
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'{hide_link(url)}',
                                        reply_markup=method_payment, parse_mode = 'HTML')

        elif c.data == 'withdrawal':

            url = 'https://telegra.ph/file/3371fbe3a76e818de86e2.jpg'

            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

            await bot.answer_callback_query(c.id)
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Seu saldo: <b>{balance} 🪙</b> {hide_link(url)}',
                                        reply_markup=output_money, parse_mode = 'HTML')

        elif c.data == 'bt54':

            balance = cursor.execute("SELECT balance FROM users").fetchone()[0]

            await bot.answer_callback_query(c.id)
            await bot.send_message(chat_id,
                                   f'Pedido em análise ✅ \n\n Método de saque: Qiwi 🟧\n\n Valor: *{balance} * \n\n Status: *em análise* 🔄',
                                   parse_mode="Markdown")

        elif c.data == 'bt55':

            balance = cursor.execute("SELECT balance FROM users").fetchone()[0]

            await bot.answer_callback_query(c.id)
            await bot.send_message(chat_id,
                                   f'Pedido em análise ✅ \n\n Método de saque: cartão/banco 🟩\n\n Valor: *{balance} * \n\n Status: *em análise* 🔄',
                                   parse_mode="Markdown")

        elif c.data == 'mail':

            url = 'https://telegra.ph/file/eaf7436bc2c8feeca9e7f.jpg'

            await bot.answer_callback_query(c.id)
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                        text=f'Escolha o tipo de envio ⬇ {hide_link(url)}',
                                        reply_markup=sending_kb, parse_mode='HTML')

        elif c.data == 'old':

            await bot.answer_callback_query(c.id)

            try:

                await sending(c.message)

            except:

                await bot.send_message(chat_id, 'Você ainda não criou um envio ❗')

        elif c.data == 'new':

            await bot.answer_callback_query(c.id)
            await TestStates.mail.set()
            await bot.send_message(chat_id, 'Envie o texto do envio 💬')

        elif c.data == 'statistics':

            url = 'https://telegra.ph/file/ff4cb9e3598df70156a79.jpg'

            for i in cursor.execute('SELECT COUNT(user_id) from users'):

                await bot.answer_callback_query(c.id)
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Quantidade de usuários: <b>{i[0]}</b> 👥 {hide_link(url)}', parse_mode='HTML',
                                          reply_markup=back_admin_panel_kb)

        elif c.data == 'promocode' or c.data == 'back_promocode':

            await bot.answer_callback_query(c.id)
            await promocode_action(chat_id, message_id)

        elif c.data == 'promocode_delete':

            await bot.answer_callback_query(c.id)
            await TestStates.delete_promo.set()
            await bot.edit_message_text(chat_id = chat_id, message_id = message_id, text = 'Envie o nome do cupom 💬', reply_markup = cancel_promo_kb)

        elif c.data == 'voucher_delete':

            await bot.answer_callback_query(c.id)
            await TestStates.delete_voucher.set()
            await bot.edit_message_text(chat_id = chat_id, message_id = message_id, text = 'Envie o nome do voucher 💬', reply_markup = cancel_voucher_kb)

        elif c.data == 'voucher' or c.data == 'back_voucher':

            await bot.answer_callback_query(c.id)
            await voucher_action(chat_id, message_id)

        elif c.data == 'activate_promo':

            await bot.answer_callback_query(c.id)
            await TestStates.activate_promo.set()
            await bot.edit_message_text(chat_id = chat_id, message_id = message_id, text = 'Digite o cupom 🎫', reply_markup = cancel_promo_kb1)

        elif c.data == 'activate_voucher':

            await bot.answer_callback_query(c.id)
            await TestStates.activate_voucher.set()
            await bot.edit_message_text(chat_id = chat_id, message_id = message_id, text = 'Digite o voucher 🎟', reply_markup = cancel_voucher_kb1)

        elif c.data == 'users':

            await bot.answer_callback_query(c.id)
            await users_actions(chat_id, message_id)

        elif c.data == 'user_ban':

            await bot.answer_callback_query(c.id)
            await TestStates.user_ban.set()
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Envie @usuario ou o ID', reply_markup = cancel_user_kb)

        elif c.data == 'user_unban':

            await bot.answer_callback_query(c.id)
            await TestStates.user_unban.set()
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Envie @usuario ou o ID', reply_markup = cancel_user_kb)

        elif c.data == 'add_admin':

            await bot.answer_callback_query(c.id)
            await TestStates.add_admin.set()
            await bot.edit_message_text(chat_id = chat_id, message_id = message_id, text = 'Envie o ID ou @usuario para promover a admin 💬', reply_markup = cancel_admin_kb)

        elif c.data == 'delete_admin':

            await bot.answer_callback_query(c.id)
            await TestStates.delete_admin.set()
            await bot.edit_message_text(chat_id = chat_id, message_id = message_id, text = 'Envie o ID ou @usuario para remover o admin 💬', reply_markup = cancel_admin_kb)

        elif c.data == 'half_money':

            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if balance >= 150:

                try:

                    form = cursor.execute('SELECT requisites FROM forms WHERE user_id = ?', (chat_id,)).fetchone()[0]
                    await c.answer('Já existe um saque pendente ⚠')

                except:

                    method = cursor.execute("SELECT method FROM info WHERE user_id = ?", (chat_id,)).fetchone()[0]
                    await bot.answer_callback_query(c.id)
                    await TestStates.amount.set()
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                text=f'Envie o valor do saque 📮 \n\n Métodos disponíveis: *{method}*',
                                                parse_mode='Markdown')

            else:

                await c.answer('Saldo insuficiente ⚠')

        elif c.data == 'all_money':

            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

            if balance >= 150:

                try:

                    form = cursor.execute('SELECT requisites FROM forms WHERE user_id = ?', (chat_id,)).fetchone()[0]
                    await c.answer('Já existe um saque pendente ⚠')

                except:

                    await bot.answer_callback_query(c.id)
                    await TestStates.requisites_v1.set()
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                text=f'Envie os dados de pagamento 📮',
                                                parse_mode='Markdown')

            else:

                await c.answer('Saldo insuficiente ⚠')

        elif c.data == 'card':

            await bot.answer_callback_query(c.id)
            await TestStates.card.set()
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                        text=f'Envie o valor do depósito', reply_markup=cancel_payment,
                                        parse_mode='Markdown')

        elif c.data == 'qiwi':

            await bot.answer_callback_query(c.id)
            await TestStates.qiwi.set()
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                        text=f'Envie o valor do depósito', reply_markup=cancel_payment,
                                        parse_mode='Markdown')

        elif c.data == 'youmoney':

            await bot.answer_callback_query(c.id)
            await TestStates.youmoney.set()
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                        text=f'Envie o valor do depósito', reply_markup=cancel_payment,
                                        parse_mode='Markdown')

        elif c.data == 'bitcoin':

            await bot.answer_callback_query(c.id)
            await TestStates.bitcoin.set()
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                        text=f'Obs.: pagamento na carteira Coinbase ⚠\n\nEnvie o valor do depósito', reply_markup=cancel_payment,
                                        parse_mode='Markdown')
        elif c.data == 'crystalpay':

            await bot.answer_callback_query(c.id)
            await TestStates.crystalpay.set()
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                        text=f'Envie o valor do depósito', reply_markup=cancel_payment,
                                        parse_mode='Markdown')

        elif c.data == 'cancel_payment':

            await bot.answer_callback_query(c.id)
            await state.finish()
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='💳 Escolha o método de depósito ⬇',
                                        reply_markup=method_payment)

        elif c.data == 'cancel_user':

            await bot.answer_callback_query(c.id)
            await state.finish()
            await users_actions(chat_id, message_id)

        elif c.data == 'cancel_promo':

            await bot.answer_callback_query(c.id)
            await state.finish()
            await promocode_action(chat_id, message_id)

        elif c.data == 'cancel_voucher':

            await bot.answer_callback_query(c.id)
            await state.finish()
            await voucher_action(chat_id, message_id)

        elif c.data == 'cancel_promo_activation':

            await bot.answer_callback_query(c.id)
            await state.finish()
            referals = cursor.execute('SELECT referals FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            referal_level = cursor.execute('SELECT referal_level FROM users WHERE user_id = ?', (chat_id,)).fetchone()[
                0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            referal_profit = cursor.execute('SELECT referal_profit FROM info WHERE user_id = ?', (chat_id,)).fetchone()[
                0]

            ref_link = 'https://telegram.me/{}?start={}'
            me = await bot.get_me()
            username = me.username
            ref = ref_link.format(username, c.message.from_user.id)
            url = 'https://telegra.ph/file/0cec7cc8de99e7f9ee639.jpg'

            admins = cursor.execute('SELECT user_id FROM admins').fetchall()
            users = []

            for i in admins:

                users.append(i[0])

            if chat_id in users:

                await bot.edit_message_text(chat_id = chat_id, message_id = message_id,text =
                                       f'🤖 Seu ID: <b>{chat_id}</b> \n \n💰 Seu saldo: <b>{balance} 🪙</b>\n \n👥 Indicados: <b>{referals}</b> \n \n🍬 Ganhos com indicação: <b>{referal_profit}</b> | Nível: <b>{referal_level}</b> \n \n🔗 Link de indicação: \n \n <code>{ref}</code> - <b>toque para copiar</b> {hide_link(url)}',
                                       reply_markup=admin_profile, parse_mode="HTML")

            elif chat_id in admin:

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=
                f'🤖 Seu ID: <b>{chat_id}</b> \n \n💰 Seu saldo: <b>{balance} 🪙</b>\n \n👥 Indicados: <b>{referals}</b> \n \n🍬 Ganhos com indicação: <b>{referal_profit}</b> | Nível: <b>{referal_level}</b> \n \n🔗 Link de indicação: \n \n <code>{ref}</code> - <b>toque para copiar</b> {hide_link(url)}',
                                       reply_markup=creator_profile, parse_mode="HTML")
            else:

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=
                f'🤖 Seu ID: <b>{chat_id}</b> \n \n💰 Seu saldo: <b>{balance} 🪙</b>\n \n👥 Indicados: <b>{referals}</b> \n \n🍬 Ganhos com indicação: <b>{referal_profit}</b> | Nível: <b>{referal_level}</b> \n \n🔗 Link de indicação: \n \n <code>{ref}</code> - <b>toque para copiar</b> {hide_link(url)}',
                                       reply_markup=user_profile, parse_mode="HTML")

        elif c.data == 'cancel_voucher_activation':

            await bot.answer_callback_query(c.id)
            await state.finish()
            referals = cursor.execute('SELECT referals FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            referal_level = cursor.execute('SELECT referal_level FROM users WHERE user_id = ?', (chat_id,)).fetchone()[
                0]
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            referal_profit = cursor.execute('SELECT referal_profit FROM info WHERE user_id = ?', (chat_id,)).fetchone()[
                0]

            ref_link = 'https://telegram.me/{}?start={}'
            me = await bot.get_me()
            username = me.username
            ref = ref_link.format(username, c.message.from_user.id)
            url = 'https://telegra.ph/file/0cec7cc8de99e7f9ee639.jpg'

            admins = cursor.execute('SELECT user_id FROM admins').fetchall()
            users = []

            for i in admins:
                users.append(i[0])

            if chat_id in users:

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=
                f'🤖 Seu ID: <b>{chat_id}</b> \n \n💰 Seu saldo: <b>{balance} 🪙</b>\n \n👥 Indicados: <b>{referals}</b> \n \n🍬 Ganhos com indicação: <b>{referal_profit}</b> | Nível: <b>{referal_level}</b> \n \n🔗 Link de indicação: \n \n <code>{ref}</code> - <b>toque para copiar</b> {hide_link(url)}',
                                       reply_markup=admin_profile, parse_mode="HTML")

            elif chat_id in admin:

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=
                f'🤖 Seu ID: <b>{chat_id}</b> \n \n💰 Seu saldo: <b>{balance} 🪙</b>\n \n👥 Indicados: <b>{referals}</b> \n \n🍬 Ganhos com indicação: <b>{referal_profit}</b> | Nível: <b>{referal_level}</b> \n \n🔗 Link de indicação: \n \n <code>{ref}</code> - <b>toque para copiar</b> {hide_link(url)}',
                                       reply_markup=creator_profile, parse_mode="HTML")
            else:

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=
                f'🤖 Seu ID: <b>{chat_id}</b> \n \n💰 Seu saldo: <b>{balance} 🪙</b>\n \n👥 Indicados: <b>{referals}</b> \n \n🍬 Ganhos com indicação: <b>{referal_profit}</b> | Nível: <b>{referal_level}</b> \n \n🔗 Link de indicação: \n \n <code>{ref}</code> - <b>toque para copiar</b> {hide_link(url)}',
                                       reply_markup=user_profile, parse_mode="HTML")

        elif c.data == 'cancel_admin':

            output = cursor.execute('SELECT output FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

            admins = cursor.execute('SELECT user_id FROM admins').fetchall()
            users = []

            for i in admins:

                users.append(i[0])

            if chat_id in users:

                if output == 1:

                    url = 'https://telegra.ph/file/34833c89e264d968aed9f.jpg'
                    await bot.answer_callback_query(c.id)
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                text=f'Painel do administrador 🤖 {hide_link(url)}', parse_mode='HTML',
                                                reply_markup=admin_kb_on)
                else:

                    url = 'https://telegra.ph/file/34833c89e264d968aed9f.jpg'
                    await bot.answer_callback_query(c.id)
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                text=f'Painel do administrador 🤖 {hide_link(url)}', parse_mode='HTML',
                                                reply_markup=admin_kb_off)

            elif chat_id in admin:

                if output == 1:

                    url = 'https://telegra.ph/file/34833c89e264d968aed9f.jpg'
                    await bot.answer_callback_query(c.id)
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                text=f'Painel do administrador 🤖 {hide_link(url)}', parse_mode='HTML',
                                                reply_markup= creator_kb_on)
                else:

                    url = 'https://telegra.ph/file/34833c89e264d968aed9f.jpg'
                    await bot.answer_callback_query(c.id)
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                text=f'Painel do administrador 🤖 {hide_link(url)}', parse_mode='HTML',
                                                reply_markup= creator_kb_off)

        elif c.data == 'check_bill_qiwi':

            await check_payment_qiwi(c, chat_id, message_id, username)

        elif c.data == 'check_bill_youmoney':

            await check_payment_youmoney(c, chat_id, message_id)

        elif c.data == 'check_bill_bitcoin':

            await check_oplata_btc(chat_id, c, username, message_id)

        elif c.data == 'check_bill_crystalpay':

            await check_payment_crystalpay(c,chat_id, message_id)

        elif c.data == 'admin_button' or c.data == 'back_admin_panel':

            output = cursor.execute('SELECT output FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

            admins = cursor.execute('SELECT user_id FROM admins').fetchall()
            users = []

            await bot.answer_callback_query(c.id)

            for i in admins:

                users.append(i[0])

            if chat_id in users:

                if output == 1:

                    url = 'https://telegra.ph/file/34833c89e264d968aed9f.jpg'
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                text=f'Painel do administrador 🤖 {hide_link(url)}', parse_mode='HTML',
                                                reply_markup=admin_kb_on)
                else:

                    url = 'https://telegra.ph/file/34833c89e264d968aed9f.jpg'
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                text=f'Painel do administrador 🤖 {hide_link(url)}', parse_mode='HTML',
                                                reply_markup=admin_kb_off)

            elif chat_id in admin:

                if output == 1:

                    url = 'https://telegra.ph/file/34833c89e264d968aed9f.jpg'
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                text=f'Painel do administrador 🤖 {hide_link(url)}', parse_mode='HTML',
                                                reply_markup= creator_kb_on)
                else:

                    url = 'https://telegra.ph/file/34833c89e264d968aed9f.jpg'
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                text=f'Painel do administrador 🤖 {hide_link(url)}', parse_mode='HTML',
                                                reply_markup= creator_kb_off)

        elif c.data == '+':

            await bot.answer_callback_query(c.id)
            await sending(c.message)

        elif c.data == '-':

            await bot.answer_callback_query(c.id)
            await state.finish()
            await bot.send_message(chat_id, 'Envio cancelado 🚫', reply_markup = sending_kb)

        elif c.data == 'output_off':

            await bot.answer_callback_query(c.id)

            cursor.execute('UPDATE users SET output = ? WHERE user_id = ?', (1, chat_id,))
            conn.commit()

            admins = cursor.execute('SELECT user_id FROM admins').fetchall()
            users = []

            for i in admins:

                users.append(i[0])

            if chat_id in users:

                url = 'https://telegra.ph/file/34833c89e264d968aed9f.jpg'
                await bot.answer_callback_query(c.id)
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Painel do administrador 🤖 {hide_link(url)}', parse_mode='HTML',
                                            reply_markup=admin_kb_on)

            elif chat_id in admin:

                url = 'https://telegra.ph/file/34833c89e264d968aed9f.jpg'
                await bot.answer_callback_query(c.id)
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Painel do administrador 🤖 {hide_link(url)}', parse_mode='HTML',
                                            reply_markup=creator_kb_on)

        elif c.data == 'output_on':

            await bot.answer_callback_query(c.id)

            cursor.execute('UPDATE users SET output = ? WHERE user_id = ?', (0, chat_id,))
            conn.commit()

            admins = cursor.execute('SELECT user_id FROM admins').fetchall()
            users = []

            for i in admins:

                users.append(i[0])

            if chat_id in users:

                url = 'https://telegra.ph/file/34833c89e264d968aed9f.jpg'
                await bot.answer_callback_query(c.id)
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Painel do administrador 🤖 {hide_link(url)}', parse_mode='HTML',
                                            reply_markup=admin_kb_off)

            elif chat_id in admin:

                url = 'https://telegra.ph/file/34833c89e264d968aed9f.jpg'
                await bot.answer_callback_query(c.id)
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Painel do administrador 🤖 {hide_link(url)}', parse_mode='HTML',
                                            reply_markup=creator_kb_off)

        elif c.data == 'user_increase_balance':

            await bot.answer_callback_query(c.id)
            await TestStates.user_increase_balance.set()
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                        text=f'Envie @usuario ou ID e o valor 🗯', reply_markup=cancel_user_kb,
                                        parse_mode='Markdown')

        elif c.data == 'user_decrease_balance':

            await bot.answer_callback_query(c.id)
            await TestStates.user_decrease_balance.set()
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                        text=f'Envie @usuario ou ID e o valor 🗯', reply_markup=cancel_user_kb,
                                        parse_mode='Markdown')

        elif c.data == 'promocode_create':

            await bot.answer_callback_query(c.id)
            await TestStates.promo.set()
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                        text=f'Envie o nome do cupom 💬', parse_mode='Markdown', reply_markup = cancel_promo_kb)

        elif c.data == 'voucher_create':

            await bot.answer_callback_query(c.id)
            await TestStates.voucher.set()
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                        text=f'Envie o nome do voucher 💬', parse_mode='Markdown', reply_markup = cancel_voucher_kb)

        elif c.data == 'zero':

            await bot.answer_callback_query(c.id)
            await roulette_zero(chat_id, message_id, c)

        elif c.data == 'even':

            await bot.answer_callback_query(c.id)
            await roulette_even(chat_id, message_id, c)

        elif c.data == 'odd':

            await bot.answer_callback_query(c.id)
            await roulette_odd(chat_id, message_id, c)

        elif c.data == 'red':

            await bot.answer_callback_query(c.id)
            await roulette_red(chat_id, message_id, c)

        elif c.data == 'black':

            await bot.answer_callback_query(c.id)
            await roulette_black(chat_id, message_id, c)

        elif c.data == '112':

            await bot.answer_callback_query(c.id)
            await roulette_112(chat_id, message_id, c)

        elif c.data == '1324':

            await bot.answer_callback_query(c.id)
            await roulette_1324(chat_id, message_id, c)

        elif c.data == '2536':

            await bot.answer_callback_query(c.id)
            await roulette_2536(chat_id, message_id, c)

        elif c.data == '1936':

            await bot.answer_callback_query(c.id)
            await roulette_1936(chat_id, message_id, c)

        elif c.data == '118':

            await bot.answer_callback_query(c.id)
            await roulette_118(chat_id, message_id, c)

        elif c.data == 'forms':

            await forms_action(chat_id, c.message, c)

        elif c.data == 'apples':

            await apples(chat_id, message_id)

        elif c.data == 'apple_ok':

            await check_apples(chat_id, message_id, c)

        elif c.data == 'balance_menu' or c.data == 'back_balance':

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            try:

                st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            except TypeError:

                demo_list = [chat_id, 0, 0, 0]

                cursor.execute("INSERT INTO demo VALUES (?, ?, ?, ?) ;", demo_list)
                conn.commit()

            st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            url = 'https://telegra.ph/file/9a00ba2c709c1a28d0f74.jpg'

            if st == 1:

                await  bot.answer_callback_query(c.id)
                await bot.edit_message_text(chat_id = chat_id, message_id = message_id, text =
                                            f'{hide_link(url)}', reply_markup = balance_menu_on, parse_mode = 'HTML')

            elif st == 0:

                await  bot.answer_callback_query(c.id)
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=
                f'{hide_link(url)}', reply_markup=balance_menu_off, parse_mode='HTML')

        elif c.data == 'demobalance_get':

            await getting_demobalance(chat_id, c)

        elif c.data == 'demobalance_on':

            await c.answer('Agora você joga com saldo real 💬')

            url = 'https://telegra.ph/file/9a00ba2c709c1a28d0f74.jpg'

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute('UPDATE demo SET state = ? WHERE user_id = ?', (0, chat_id,))
            conn.commit()

            cursor.close()

            await  bot.answer_callback_query(c.id)
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=
            f'{hide_link(url)}', reply_markup = balance_menu_off, parse_mode='HTML')

        elif c.data == 'demobalance_off':

            await c.answer('Agora você joga com saldo demo 💬')

            url = 'https://telegra.ph/file/9a00ba2c709c1a28d0f74.jpg'

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute('UPDATE demo SET state = ? WHERE user_id = ?', (1, chat_id,))
            conn.commit()

            cursor.close()

            await  bot.answer_callback_query(c.id)
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=
            f'{hide_link(url)}', reply_markup = balance_menu_on, parse_mode='HTML')

        elif c.data == c.data:

            if c.data.split(':')[1] == 'reject':

                await bot.edit_message_text(chat_id = chat_id, message_id = message_id, text = 'Saque recusado ❎')
                await withdrawal_reject(c.data.split(':')[0])

            elif c.data.split(':')[1] == 'accept':

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='Saque aprovado ✅')
                await withdrawal_accept(c.data.split(':')[0])

            elif c.data.split(':')[1] == 'check':

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (c.data.split(':')[0],)).fetchone()[0]

                cursor.close()

                await c.answer(f'Saldo do usuário = {balance} 🪙')

    else:
        await bot.answer_callback_query(c.id)
        await bot.send_message(chat_id, 'Você foi banido 🚫')



if __name__ == "__main__":
    executor.start_polling(dp)
