import asyncio
import random
import sqlite3

from random import *

from main import *
from config import *
from buttons import *

async def do_bet(game, chat_id, message_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if game == 'roulette':

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙', reply_markup = bet_roulette_kb)

    elif game == 'bowling':

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙', reply_markup=bet_bowling_kb)

    elif game == 'darts':

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_darts_kb)

    elif game == 'football':

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_football_kb)

    elif game == 'basketball':

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_basketball_kb)

    elif game == 'shell':

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_shell_kb)

    elif game == 'slots':

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_slots_kb)

    elif game == 'dice':

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_dice_kb)

    elif game == 'coin':

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup = bet_coin_kb)

    elif game == 'jackpot':

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup = bet_jackpot_kb)

async def do_bet_increase(game, chat_id, message_id):

    if game == 'roulette':

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
        cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet + 25, chat_id,))
        conn.commit()
        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

        cursor.close()

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_roulette_kb)

    elif game == 'bowling':

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
        cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet + 25, chat_id,))
        conn.commit()
        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

        cursor.close()

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_bowling_kb)

    elif game == 'darts':

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
        cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet + 25, chat_id,))
        conn.commit()
        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

        cursor.close()

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_darts_kb)

    elif game == 'football':

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
        cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet + 25, chat_id,))
        conn.commit()
        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

        cursor.close()

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_football_kb)

    elif game == 'basketball':

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
        cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet + 25, chat_id,))
        conn.commit()
        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

        cursor.close()

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_basketball_kb)

    elif game == 'shell':

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
        cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet + 25, chat_id,))
        conn.commit()
        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

        cursor.close()

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_shell_kb)

    elif game == 'slots':

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
        cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet + 25, chat_id,))
        conn.commit()
        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

        cursor.close()

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_slots_kb)

    elif game == 'dice':

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
        cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet + 25, chat_id,))
        conn.commit()
        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

        cursor.close()

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_dice_kb)

    elif game == 'coin':

        conn = sqlite3.connect('bebra.db', check_same_thread=False)
        cursor = conn.cursor()

        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
        cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet + 25, chat_id,))
        conn.commit()
        bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

        cursor.close()

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                    reply_markup=bet_coin_kb)

async def do_bet_decrease(game, c, chat_id, message_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if bet <= 25:

        await c.answer('A aposta não pode ser menor que o mínimo ⚠')

    else:

        await bot.answer_callback_query(c.id)

        if game == 'roulette':

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet - 25, chat_id,))
            conn.commit()
            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                        reply_markup=bet_roulette_kb)

        elif game == 'bowling':

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet - 25, chat_id,))
            conn.commit()
            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                        reply_markup=bet_bowling_kb)

        elif game == 'darts':

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet - 25, chat_id,))
            conn.commit()
            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                        reply_markup=bet_darts_kb)

        elif game == 'football':

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet - 25, chat_id,))
            conn.commit()
            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                        reply_markup=bet_football_kb)

        elif game == 'basketball':

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet - 25, chat_id,))
            conn.commit()
            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                        reply_markup=bet_basketball_kb)

        elif game == 'shell':

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet - 25, chat_id,))
            conn.commit()
            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                        reply_markup=bet_shell_kb)

        elif game == 'slots':

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet - 25, chat_id,))
            conn.commit()
            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                        reply_markup=bet_slots_kb)

        elif game == 'dice':

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet - 25, chat_id,))
            conn.commit()
            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                        reply_markup=bet_dice_kb)

        elif game == 'coin':

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute('UPDATE info SET bet = ? WHERE user_id = ?', (bet - 25, chat_id,))
            conn.commit()
            bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f'Sua aposta = {bet} 🪙',
                                        reply_markup=bet_coin_kb)

async def slots(c, chat_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    cursor.close()

    if st == 0:

        if balance > 0:

            bot_data = await bot.send_dice(chat_id, emoji='🎰')
            bot_data = bot_data['dice']['value']

            await asyncio.sleep(2)

            if bot_data == 43 or bot_data == 22 or bot_data == 64 or bot_data == 1:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet * 16, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id, f'*JACKPOT* 💰 \n\nSeu prêmio: *{bet * 16} 🪙* \n\n Seu saldo: *{balance} 🪙*', parse_mode='Markdown', reply_markup = slots_kb)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id, f'*Você perdeu* 🥴 \n\nSua perda: *- {bet} 🪙* \n\n Seu saldo: *{balance} 🪙*', parse_mode='Markdown', reply_markup = slots_kb)

        else:

            await c.answer('⚠ Deposite para continuar ⚠', show_alert=True)

    elif st == 1:

        if demobalance > 0:

            bot_data = await bot.send_dice(chat_id, emoji='🎰')
            bot_data = bot_data['dice']['value']

            await asyncio.sleep(2)

            if bot_data == 43 or bot_data == 22 or bot_data == 64 or bot_data == 1:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet * 16, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*JACKPOT* 💰 \n\nSeu prêmio: *{bet * 16} 🪙* \n\n Seu saldo demo: *{demobalance} 🪙*',
                                       parse_mode='Markdown', reply_markup=slots_kb)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Você perdeu* 🥴 \n\nSua perda: *- {bet} 🪙* \n\n Seu saldo demo: *{demobalance} 🪙*',
                                       parse_mode='Markdown', reply_markup=slots_kb)

        else:

            await c.answer('⚠ Saldo demo esgotado ⚠', show_alert=True)

async def darts(c, chat_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    cursor.close()

    if st == 0:

        if balance > 0:

            bot_data = await bot.send_dice(chat_id, emoji='🎯')
            bot_data = bot_data['dice']['value']

            await asyncio.sleep(4.0)

            if bot_data == 1 or bot_data == 2 or bot_data == 3 or bot_data == 4 or bot_data == 5:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Você errou* 🥴 \n\nSua perda: *- {bet} 🪙* \n\n Seu saldo: *{balance}* 🪙',
                                       parse_mode='Markdown', reply_markup = darts_kb)

            elif bot_data == 6:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet * 6, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id, f'*Na mosca 🍏*\n\nSeu prêmio: *+ {bet * 6} 🪙* \n\n Seu saldo: *{balance} 🪙*',
                                       parse_mode='Markdown', reply_markup = darts_kb)
        else:

            await c.answer('⚠ Deposite para continuar ⚠', show_alert=True)

    elif st == 1:

        if demobalance > 0:

            bot_data = await bot.send_dice(chat_id, emoji='🎯')
            bot_data = bot_data['dice']['value']

            await asyncio.sleep(4.0)

            if bot_data == 1 or bot_data == 2 or bot_data == 3 or bot_data == 4 or bot_data == 5:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Você errou* 🥴 \n\nSua perda: *- {bet} 🪙* \n\n Seu saldo demo: *{demobalance}* 🪙',
                                       parse_mode='Markdown', reply_markup=darts_kb)

            elif bot_data == 6:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet * 6, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Na mosca 🍏*\n\nSeu prêmio: *+ {bet * 6} 🪙* \n\n Seu saldo demo: *{demobalance} 🪙*',
                                       parse_mode='Markdown', reply_markup=darts_kb)
        else:

            await c.answer('Saldo demo esgotado ⚠', show_alert=True)

async def football(c, chat_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    cursor.close()

    if st == 0:

        if balance > 0:

            bot_data = await bot.send_dice(chat_id, emoji='⚽')
            bot_data = bot_data['dice']['value']
            print(bot_data)
            await asyncio.sleep(4.5)

            if bot_data == 1 or bot_data == 2 or bot_data == 6 or bot_data == 3:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Não entrou* 🥴 \n\nSua perda: *- {bet} 🪙* \n\n Seu saldo: *{balance}* 🪙',
                                       parse_mode='Markdown', reply_markup = football_kb)

            elif bot_data == 4 or  bot_data == 5 or bot_data:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet * 3, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id, f'*GOOOL 🏆*\n\nSeu prêmio: *+ {bet * 3}* \n\n Seu saldo: *{balance} 🪙*',
                                       parse_mode='Markdown', reply_markup = football_kb)

        else:

            await c.answer('⚠ Deposite para continuar ⚠', show_alert=True)

    elif st == 1:

        if demobalance > 0:

            bot_data = await bot.send_dice(chat_id, emoji='⚽')
            bot_data = bot_data['dice']['value']

            await asyncio.sleep(4.5)

            if bot_data == 1 or bot_data == 2 or bot_data == 6:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Não entrou* 🥴 \n\nSua perda: *- {bet} 🪙* \n\n Seu saldo demo: *{demobalance}* 🪙',
                                       parse_mode='Markdown', reply_markup = football_kb)

            elif bot_data == 4 or  bot_data == 5 or bot_data == 3:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet * 3, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id, f'*GOOOL 🏆*\n\nSeu prêmio: *+ {bet * 3}* \n\n Seu saldo demo: *{demobalance} 🪙*',
                                       parse_mode='Markdown', reply_markup = football_kb)

        else:

            await c.answer('Saldo demo esgotado ⚠', show_alert=True)

async def basketball(c, chat_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    cursor.close()

    if st == 0:

        if balance > 0:

            bot_data = await bot.send_dice(chat_id, emoji = '🏀')
            bot_data = bot_data['dice']['value']
            print(bot_data)
            await asyncio.sleep(4.5)

            if bot_data == 1 or bot_data == 2 or bot_data == 6 or bot_data == 3:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Você errou* 🥴 \n\nSua perda: *- {bet} 🪙* \n\n Seu saldo: *{balance}* 🪙',
                                       parse_mode='Markdown', reply_markup = basketball_kb)

            elif bot_data == 4 or  bot_data == 5:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet * 3, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id, f'*Cesta de 3 🎉*\n\nSeu prêmio: *+ {bet * 3}* \n\n Seu saldo: *{balance} 🪙*',
                                       parse_mode='Markdown', reply_markup = basketball_kb)

        else:

            await c.answer('⚠ Deposite para continuar ⚠', show_alert=True)

    elif st == 1:

        if demobalance > 0:

            bot_data = await bot.send_dice(chat_id, emoji='🏀')
            bot_data = bot_data['dice']['value']

            await asyncio.sleep(4.5)

            if bot_data == 1 or bot_data == 2 or bot_data == 6 or bot_data == 3:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Você errou* 🥴 \n\nSua perda: *- {bet} 🪙* \n\n Seu saldo demo: *{demobalance}* 🪙',
                                       parse_mode='Markdown', reply_markup = basketball_kb)

            elif bot_data == 4 or bot_data == 5:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet * 3, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id, f'*Cesta de 3 🎉*\n\nSeu prêmio: *+ {bet * 3}* \n\n Seu saldo demo: *{demobalance} 🪙*',
                                       parse_mode='Markdown', reply_markup = basketball_kb)

        else:

            await c.answer('Saldo demo esgotado ⚠', show_alert=True)

async def bowling(c, chat_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            bot_data = await bot.send_dice(chat_id, emoji='🎳')
            bot_data = bot_data['dice']['value']

            await asyncio.sleep(4)

            if bot_data == 1 or bot_data == 2 or bot_data == 3 or bot_data == 4 or bot_data == 5:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Você perdeu* 🥴 \n\nSua perda: *- {bet} 🪙* \n\n Seu saldo: *{balance}* 🪙',
                                       parse_mode='Markdown', reply_markup = bowling_kb)

            elif bot_data == 6:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet * 6, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'🎳  STRIKE 🎳    \n\n*Você ganhou* 🤩 \n\nSeu prêmio: *+ {bet * 6} 🪙* \n\n Seu saldo: *{balance} 🪙*',
                                       parse_mode='Markdown', reply_markup= bowling_kb)
        else:

            await c.answer('⚠ Deposite para continuar ⚠', show_alert=True)\

    elif st == 1:

        if demobalance > 0:

            bot_data = await bot.send_dice(chat_id, emoji='🎳')
            bot_data = bot_data['dice']['value']

            await asyncio.sleep(4)

            if bot_data == 1 or bot_data == 2 or bot_data == 3 or bot_data == 4 or bot_data == 5:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Você perdeu* 🥴 \n\nSua perda: *- {bet} 🪙* \n\n Seu saldo demo: *{demobalance}* 🪙',
                                       parse_mode='Markdown', reply_markup=bowling_kb)

            elif bot_data == 6:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet * 6, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'🎳  STRIKE 🎳    \n\n*Você ganhou* 🤩 \n\nSeu prêmio: *+ {bet * 6} 🪙* \n\n Seu saldo demo: *{demobalance} 🪙*',
                                       parse_mode='Markdown', reply_markup=bowling_kb)
        else:

            await c.answer('Saldo demo esgotado ⚠', show_alert=True)

async def dice(c, chat_id):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            await bot.send_message(chat_id, 'Seu dado ⬇')
            bot_data = await bot.send_dice(chat_id)
            bot_data = bot_data['dice']['value']

            await bot.send_message(chat_id, 'Dado do oponente ⬇')
            user_data = await bot.send_dice(chat_id)
            user_data = user_data['dice']['value']

            await asyncio.sleep(4)

            if bot_data < user_data:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Você perdeu* 🥴 \n\nSua perda: * - {bet}* \n\n Seu saldo: *{balance}* 🪙',
                                       parse_mode='Markdown', reply_markup = dice_kb)

            elif bot_data > user_data:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Você ganhou* 🤩 \n\nSeu prêmio: *+ {bet}* \n\n Seu saldo: *{balance}* 🪙',
                                       parse_mode='Markdown', reply_markup = dice_kb)

            else:
                await bot.send_message(chat_id, f'*Empate!* \n\nSeu saldo: *{balance}*', parse_mode='Markdown',
                                       reply_markup = dice_kb)

        else:

            await c.answer('⚠ Deposite para continuar ⚠', show_alert=True)

    elif st == 1:


        if demobalance > 0:

            await bot.send_message(chat_id, 'Seu dado ⬇')
            bot_data = await bot.send_dice(chat_id)
            bot_data = bot_data['dice']['value']

            await bot.send_message(chat_id, 'Dado do oponente ⬇')
            user_data = await bot.send_dice(chat_id)
            user_data = user_data['dice']['value']

            await asyncio.sleep(4)

            if bot_data < user_data:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Você perdeu* 🥴 \n\nSua perda: * - {bet}* \n\n Seu saldo demo: *{demobalance}* 🪙',
                                       parse_mode='Markdown', reply_markup=dice_kb)

            elif bot_data > user_data:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.close()

                await bot.send_message(chat_id,
                                       f'*Você ganhou* 🤩 \n\nSeu prêmio: *+ {bet}* \n\n Seu saldo demo: *{demobalance}* 🪙',
                                       parse_mode='Markdown', reply_markup=dice_kb)

            else:
                await bot.send_message(chat_id, f'*Empate!* \n\nSeu saldo demo: *{demobalance}*', parse_mode='Markdown',
                                       reply_markup=dice_kb)

        else:

            await c.answer('Saldo demo esgotado ⚠', show_alert=True)

async def shell(chat_id, message_id, c):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                        text='Adivinhe em qual copo está o *prêmio*:\n \n          📦                    📦                    📦',
                                        parse_mode="Markdown", reply_markup= shell_buttons)

        else:

            await c.answer('⚠ Deposite para continuar ⚠', show_alert=True)

    elif st == 1:

        if demobalance > 0:

            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                        text='Adivinhe em qual copo está o *prêmio*:\n \n          📦                    📦                    📦',
                                        parse_mode="Markdown", reply_markup=shell_buttons)

        else:

            await c.answer('Saldo demo esgotado ⚠')

async def shell_first(c, chat_id, message_id):

    test = ['❌', '❌', '💰']

    a = choice(test)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            if a == test[0]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Não foi dessa vez* 🥴 \n\nSua perda: *- {bet} 🪙*\n\nSeu saldo: *{balance} 🪙* \n \n     {a}                  📦                  📦',
                                            parse_mode='Markdown', reply_markup = shell_kb)

            elif a == test[1]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Não foi dessa vez* 🥴 \n\nSua perda: *- {bet} 🪙\n\nSeu saldo: *{balance} 🪙* \n \n     {a}                  📦                  📦',
                                            parse_mode='Markdown', reply_markup=shell_kb)

            elif a == test[2]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet * 3, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Você acertou* 🤩 \n\nSeu prêmio: *+ {bet * 3} 🪙* \n\nSeu saldo: *{balance} 🪙* \n \n          {a}                    📦                    📦',
                                            parse_mode='Markdown', reply_markup = shell_kb)

        else:

            await c.answer('⚠ Deposite para continuar ⚠')

    elif st == 1:

        if demobalance > 0:

            if a == test[0]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Não foi dessa vez* 🥴 \n\nSua perda: *- {bet} 🪙*\n\nSeu saldo demo: *{demobalance} 🪙* \n \n     {a}                  📦                  📦',
                                            parse_mode='Markdown', reply_markup=shell_kb)

            elif a == test[1]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Não foi dessa vez* 🥴 \n\nSua perda: *- {bet} 🪙\n\nSeu saldo demo: *{demobalance} 🪙* \n \n     {a}                  📦                  📦',
                                            parse_mode='Markdown', reply_markup=shell_kb)

            elif a == test[2]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet * 3, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Você acertou* 🤩 \n\nSeu prêmio: *+ {bet * 3} 🪙* \n\nSeu saldo demo: *{demobalance} 🪙* \n \n          {a}                    📦                    📦',
                                            parse_mode='Markdown', reply_markup=shell_kb)

        else:

            await c.answer('Saldo demo esgotado ⚠')

async def shell_second(c, chat_id, message_id):

    test = ['❌', '❌', '💰']

    a = choice(test)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            if a == test[0]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Não foi dessa vez* 🥴 \n\nSua perda: *- {bet} 🪙*\n\nSeu saldo: *{balance} 🪙* \n \n     {a}                  📦                  📦',
                                            parse_mode='Markdown', reply_markup = shell_kb)

            elif a == test[1]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Não foi dessa vez* 🥴 \n\nSua perda: *- {bet} 🪙\n\nSeu saldo: *{balance} 🪙* \n \n     {a}                  📦                  📦',
                                            parse_mode='Markdown', reply_markup=shell_kb)

            elif a == test[2]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet * 3, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Você acertou* 🤩 \n\nSeu prêmio: *+ {bet * 3} 🪙* \n\nSeu saldo: *{balance} 🪙* \n \n          {a}                    📦                    📦',
                                            parse_mode='Markdown', reply_markup = shell_kb)

        else:

            await c.answer('⚠ Deposite para continuar ⚠')

    elif st == 1:

        if demobalance > 0:

            if a == test[0]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Não foi dessa vez* 🥴 \n\nSua perda: *- {bet} 🪙*\n\nSeu saldo demo: *{demobalance} 🪙* \n \n     {a}                  📦                  📦',
                                            parse_mode='Markdown', reply_markup=shell_kb)

            elif a == test[1]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Não foi dessa vez* 🥴 \n\nSua perda: *- {bet} 🪙\n\nSeu saldo demo: *{demobalance} 🪙* \n \n     {a}                  📦                  📦',
                                            parse_mode='Markdown', reply_markup=shell_kb)

            elif a == test[2]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet * 3, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Você acertou* 🤩 \n\nSeu prêmio: *+ {bet * 3} 🪙* \n\nSeu saldo demo: *{demobalance} 🪙* \n \n          {a}                    📦                    📦',
                                            parse_mode='Markdown', reply_markup=shell_kb)

        else:

            await c.answer('Saldo demo esgotado ⚠')


async def shell_third(c, chat_id, message_id):

    test = ['❌', '❌', '💰']

    a = choice(test)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            if a == test[0]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Não foi dessa vez* 🥴 \n\nSua perda: *- {bet} 🪙*\n\nSeu saldo: *{balance} 🪙* \n \n     {a}                  📦                  📦',
                                            parse_mode='Markdown', reply_markup = shell_kb)

            elif a == test[1]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Não foi dessa vez* 🥴 \n\nSua perda: *- {bet} 🪙\n\nSeu saldo: *{balance} 🪙* \n \n     {a}                  📦                  📦',
                                            parse_mode='Markdown', reply_markup=shell_kb)

            elif a == test[2]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet * 3, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Você acertou* 🤩 \n\nSeu prêmio: *+ {bet * 3} 🪙* \n\nSeu saldo: *{balance} 🪙* \n \n          {a}                    📦                    📦',
                                            parse_mode='Markdown', reply_markup = shell_kb)

        else:

            await c.answer('⚠ Deposite para continuar ⚠')

    elif st == 1:

        if demobalance > 0:

            if a == test[0]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Não foi dessa vez* 🥴 \n\nSua perda: *- {bet} 🪙*\n\nSeu saldo demo: *{demobalance} 🪙* \n \n     {a}                  📦                  📦',
                                            parse_mode='Markdown', reply_markup=shell_kb)

            elif a == test[1]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Não foi dessa vez* 🥴 \n\nSua perda: *- {bet} 🪙\n\nSeu saldo demo: *{demobalance} 🪙* \n \n     {a}                  📦                  📦',
                                            parse_mode='Markdown', reply_markup=shell_kb)

            elif a == test[2]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet * 3, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'*Você acertou* 🤩 \n\nSeu prêmio: *+ {bet * 3} 🪙* \n\nSeu saldo demo: *{demobalance} 🪙* \n \n          {a}                    📦                    📦',
                                            parse_mode='Markdown', reply_markup=shell_kb)

        else:

            await c.answer('Saldo demo esgotado ⚠')

async def roulette_even(chat_id, message_id, c):

    test = ['⚫', '🔴']

    number = randint(1,36)
    color = choice(test)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            if number % 2 != 0:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Deposite para continuar ⚠', show_alert=True)

    elif st == 1:

        if demobalance > 0:

            if number % 2 != 0:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Saldo demo esgotado ⚠', show_alert=True)

async def roulette_odd(chat_id, message_id, c):

    test = ['⚫', '🔴']

    number = randint(1,36)
    color = choice(test)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            if number % 2 == 0:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Deposite para continuar ⚠', show_alert=True)

    elif st == 1:

        if demobalance > 0:

            if number % 2 == 0:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Saldo demo esgotado ⚠', show_alert=True)

async def roulette_red(chat_id, message_id, c):

    test = ['⚫', '🔴']

    number = randint(1,36)
    color = choice(test)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            if color == test[0]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Deposite para continuar ⚠')

    elif st == 1:

        if demobalance > 0:

            if color == test[0]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Saldo demo esgotado ⚠')

async def roulette_black(chat_id, message_id, c):

    test = ['⚫', '🔴']

    number = randint(1,36)
    color = choice(test)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            if color == test[1]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Deposite para continuar ⚠')

    elif st == 1:

        if demobalance > 0:

            if color == test[1]:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Saldo demo esgotado ⚠')

async def roulette_112(chat_id, message_id, c):

    test = ['⚫', '🔴']

    number = randint(1,36)
    color = choice(test)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            if number > 13:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Deposite para continuar ⚠')

    elif st == 1:

        if demobalance > 0:

            if number > 13:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Saldo demo esgotado ⚠')

async def roulette_1324(chat_id, message_id, c):

    test = ['⚫', '🔴']

    number = randint(1,36)
    color = choice(test)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            if 24 < number or number < 13:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Deposite para continuar ⚠')

    elif st == 1:

        if demobalance > 0:

            if 24 < number or number < 13:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Saldo demo esgotado ⚠')

async def roulette_2536(chat_id, message_id, c):

    test = ['⚫', '🔴']

    number = randint(1,36)
    color = choice(test)


    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            if number < 25:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Deposite para continuar ⚠')

    elif st == 1:

        if demobalance > 0:

            if number < 25:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Saldo demo esgotado ⚠')

async def roulette_118(chat_id, message_id, c):

    test = ['⚫', '🔴']

    number = randint(1,36)
    color = choice(test)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            if number > 18:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Deposite para continuar ⚠')

    elif st == 1:

        if demobalance > 0:

            if number > 18:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Saldo demo esgotado ⚠')

async def roulette_1936(chat_id, message_id, c):

    test = ['⚫', '🔴']

    number = randint(1,36)
    color = choice(test)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            if 19 > number < 36:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo: *{balance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Deposite para continuar ⚠')

    elif st == 1:

        if demobalance > 0:

            if 19 > number < 36:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você perdeu | *{number}* {color} \n\nSua perda: *- {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Você ganhou | *{number}* {color} \n\nSeu prêmio: *+ {bet} 🪙* \n\nSaldo demo: *{demobalance}* 🪙',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Saldo demo esgotado ⚠')

async def roulette_zero(chat_id, message_id, c):

    test = ['⚫', '🔴']

    number = randint(0,36)
    color = choice(test)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
    demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    if st == 0:

        if balance > 0:

            if number != 0:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Resultado: {number} {color} \n\n *Você* perdeu 🥴 \n\nSeu saldo: *{balance} 🪙*',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet * 16, chat_id,))
                conn.commit()
                balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Resultado: {number} {color} \n\n *Você* ganhou 🤩 \n\nSeu saldo demo: *{balance} 🪙*',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Deposite para continuar ⚠')

    elif st == 1:

        if demobalance > 0:

            if number != 0:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance - bet, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Resultado: {number} {color} \n\n *Você* perdeu 🥴 \n\nSeu saldo demo: *{demobalance} 🪙*',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

            else:

                conn = sqlite3.connect('bebra.db', check_same_thread=False)
                cursor = conn.cursor()

                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
                cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet * 16, chat_id,))
                conn.commit()
                demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

                cursor.close()

                await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=f'Resultado: {number} {color} \n\n *Você* ganhou 🤩 \n\nSeu saldo demo: *{demobalance} 🪙*',
                                            parse_mode='Markdown', reply_markup=roulette_kb1)

        else:

            await c.answer('Deposite para continuar ⚠')

async def coin_tail(chat_id, message_id, c):

    eagle = 'CAACAgIAAxkBAAEFFJRirzvotAJ-3OT-3Qzc_d8za0xcOwAClhcAAsiE0Ui67wnmqzpt6SQE'
    tail = 'CAACAgIAAxkBAAEFFJZirzv2uEEGBIHrvTss3FRNd7p-KQACpRcAAgaN0Egkmq4OpEO-oCQE'

    b = [eagle, tail]

    a = choice(b)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    await bot.send_sticker(chat_id, a, protect_content=True)
    await asyncio.sleep(2)

    if st == 0:

        if a == b[0]:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet, chat_id,))
            conn.commit()
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.send_message(chat_id,
                                   f'*Você ganhou* 🤩 \n\nSeu prêmio: *+ {bet}* \n\n Seu saldo: *{balance}* 🪙',
                                   reply_markup=coin_kb_1, parse_mode='Markdown')
        else:
            print(2)
            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
            conn.commit()
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.send_message(chat_id,
                                   f'*Você perdeu* 🥴 \n\nSua perda: * - {bet}* \n\n Seu saldo: *{balance}* 🪙',
                                   parse_mode='Markdown', reply_markup=coin_kb_1)

    elif st == 1:

        if a == b[1]:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
            conn.commit()
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.send_message(chat_id,
                                   f'*Você ganhou* 🤩 \n\nSeu prêmio: *+ {bet}* \n\n Seu saldo demo: *{demobalance}* 🪙',
                                   reply_markup=coin_kb_1, parse_mode='Markdown')
        else:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
            conn.commit()
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.send_message(chat_id,
                                   f'*Você perdeu* 🥴 \n\nSua perda: * - {bet}* \n\n Seu saldo demo: *{demobalance}* 🪙',
                                   parse_mode='Markdown', reply_markup=coin_kb_1)

async def coin_eagle(chat_id, message_id, c):

    eagle = 'CAACAgIAAxkBAAEFFJRirzvotAJ-3OT-3Qzc_d8za0xcOwAClhcAAsiE0Ui67wnmqzpt6SQE'
    tail = 'CAACAgIAAxkBAAEFFJZirzv2uEEGBIHrvTss3FRNd7p-KQACpRcAAgaN0Egkmq4OpEO-oCQE'

    b = [eagle, tail]

    a = choice(b)

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    bet = cursor.execute('SELECT bet FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]
    st = cursor.execute('SELECT state FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

    cursor.close()

    await bot.send_sticker(chat_id, a, protect_content=True)
    await asyncio.sleep(2)

    if st == 0:

        if a == b[1]:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance + bet, chat_id,))
            conn.commit()
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.send_message(chat_id,
                                   f'*Você ganhou* 🤩 \n\nSeu prêmio: *+ {bet}* \n\n Seu saldo: *{balance}* 🪙',
                                   reply_markup=coin_kb_1, parse_mode='Markdown')
        else:
            print(2)
            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, chat_id,))
            conn.commit()
            balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.send_message(chat_id,
                                   f'*Você perdeu* 🥴 \n\nSua perda: * - {bet}* \n\n Seu saldo: *{balance}* 🪙',
                                   parse_mode='Markdown', reply_markup=coin_kb_1)

    elif st == 1:

        if a == b[0]:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
            conn.commit()
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.send_message(chat_id,
                                   f'*Você ganhou* 🤩 \n\nSeu prêmio: *+ {bet}* \n\n Seu saldo demo: *{demobalance}* 🪙',
                                   reply_markup=coin_kb_1, parse_mode='Markdown')
        else:

            conn = sqlite3.connect('bebra.db', check_same_thread=False)
            cursor = conn.cursor()

            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]
            cursor.execute("UPDATE demo SET demobalance = ? WHERE user_id = ?", (demobalance + bet, chat_id,))
            conn.commit()
            demobalance = cursor.execute('SELECT demobalance FROM demo WHERE user_id = ?', (chat_id,)).fetchone()[0]

            cursor.close()

            await bot.send_message(chat_id,
                                   f'*Você perdeu* 🥴 \n\nSua perda: * - {bet}* \n\n Seu saldo demo: *{demobalance}* 🪙',
                                   parse_mode='Markdown', reply_markup=coin_kb_1)

async def apples(chat_id, message_id):

    await bot.edit_message_text(chat_id = chat_id, message_id = message_id, text = 'Jogo', reply_markup = apple_keyboard)

async def check_apples(chat_id, message_id, c):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    winning = cursor.execute('SELECT winning FROM info WHERE user_id = ?', (chat_id,)).fetchone()[0]

    if winning == None or winning == 0:

        await bot.answer_callback_query(c.id)

        balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (chat_id,)).fetchone()[0]

        cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (balance + winning, chat_id,))
        conn.commit()

        cursor.close()

        await bot.edit_message_text(chat_id = chat_id, message_id = message_id, text = 'Texto', reply_markup = apple_keyboard)
    else:

        await c.answer('Você ainda não jogou ')

        await bot.edit_message_text(chat_id = chat_id, message_id = message_id)

async def create_jackpot(chat_id, amount, c):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (chat_id,))
    cur = cursor.fetchone()

    if cur is None:

        jackpot_list = [chat_id, None, None, None, None, None, amount, 0]

        cursor.execute("INSERT INTO payment_youmoney VALUES (?, ?, ?, ?, ?, ?, ?, ?) ;", jackpot_list)
        conn.commit()

        amount = cursor.execute('SELECT amount FROM jackpot WHERE user_id = ?', (chat_id,))
        players = cursor.execute('SELECT players FROM jackpot WHERE user_id = ?', (chat_id,))

        cursor.close()

        await bot.send_message(chat_id, f'Jogo criado\n\nJogadores: {players}\n\nPrêmio: {amount}')

    else:

        await c.answer("Você já tem um jogo criado ⚠")
'''
async def join_jackpot(chat_id, amount, c):

    conn = sqlite3.connect('bebra.db', check_same_thread=False)
    cursor = conn.cursor()

    for i in cursor.execute('SELECT founder FROM users WHERE user_id = ?', (chat_id,)).fetchall():

        if i is None:

            jackpot_list = [chat_id, None, None, None, None, None, amount, 0]

            cursor.execute("INSERT INTO payment_youmoney VALUES (?, ?, ?, ?, ?, ?, ?, ?) ;", jackpot_list)
            conn.commit()

            amount = cursor.execute('SELECT amount FROM jackpot WHERE user_id = ?', (chat_id,))
            players = cursor.execute('SELECT players FROM jackpot WHERE user_id = ?', (chat_id,))

            cursor.close()

            await bot.send_message(chat_id, f'Jogo criado\n\nJogadores: {players}\n\nPrêmio: {amount}')

        else:

            await c.answer("Você já tem um jogo criado ⚠")
'''


