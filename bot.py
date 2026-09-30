import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, Message
)

# --- تنظیمات اولیه ---
BOT_TOKEN = "8774784196:AAFi1vVNZ0xefNgdr3c-yf_TaYfqmdPYez0"
ADMIN_ID = 8852983684
BOT_USERNAME = "LuckyRoll_ir_bot"
CHANNEL_LINK = "https://t.me/LuckyRoll_IR"

CARD_NUMBER = "6221061224786881"
CARD_HOLDER = "دانیال رحمت آبادی"
TON_WALLET = "UQDatZuwI_hBFCX8tOUM1Y_5_FkOqZ_CFAJQm-Af1By98XcW"

MIN_CARD_DEPOSIT = 250000
MIN_VOUCHER_DEPOSIT = 300000
INVITE_BONUS = 30000
MAX_INVITES = 4

# --- اتصال به دیتابیس SQLite ---
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    required_turnover INTEGER DEFAULT 0,
    invited_count INTEGER DEFAULT 0,
    referrer_id INTEGER DEFAULT NULL
)
""")
conn.commit()

# --- تعاریف FSM ---
class DepositState(StatesGroup):
    waiting_for_card_receipt = State()
    waiting_for_voucher_code = State()

class WithdrawState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_card_info = State()

class BetState(StatesGroup):
    waiting_for_amount = State()

# --- کیبورد اصلی ---
def get_main_keyboard():
    kb = [
        [KeyboardButton(text="🎲 بازی تاس"), KeyboardButton(text="👤 حساب کاربری")],
        [KeyboardButton(text="💳 شارژ حساب"), KeyboardButton(text="🏧 برداشت وجه")],
        [KeyboardButton(text="👥 دعوت دوستان"), KeyboardButton(text="📢 کانال اطلاع‌‌رسانی")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- توابع کمکی دیتابیس ---
def get_user(user_id):
    cursor.execute("SELECT user_id, balance, required_turnover, invited_count, referrer_id FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if not res:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return (user_id, 0, 0, 0, None)
    return res

def update_balance(user_id, amount):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def update_turnover(user_id, amount):
    cursor.execute("UPDATE users SET required_turnover = MAX(0, required_turnover - ?) WHERE user_id = ?", (amount, user_id))
    conn.commit()

def add_required_turnover(user_id, amount):
    cursor.execute("UPDATE users SET required_turnover = required_turnover + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

# --- شروع ساخت ربات ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- دستور /start ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    args = message.text.split()
    
    user = get_user(user_id)
    
    # سیستم زیرمجموعه‌گیری
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        if referrer_id != user_id and user[4] is None:
            ref_user = get_user(referrer_id)
            if ref_user[3] < MAX_INVITES:
                cursor.execute("UPDATE users SET referrer_id = ? WHERE user_id = ?", (referrer_id, user_id))
                cursor.execute("UPDATE users SET invited_count = invited_count + 1, balance = balance + ? WHERE user_id = ?", (INVITE_BONUS, referrer_id))
                conn.commit()
                try:
                    await bot.send_message(referrer_id, f"🎉 کاربر جدیدی با لینک شما وارد شد! مبلغ {INVITE_BONUS:,} تومان هدیه به حساب شما اضافه شد.")
                except Exception:
                    pass

    welcome_text = (
        f"سلام {message.from_user.first_name} عزیز! 🎲\n\n"
        f"به ربات شرط‌بندی تاس خوش آمدید.\n"
        f"می‌توانید شانس خود را در حالت‌های زوج، فرد یا عدد دقیق آزمایش کنید.\n\n"
        f"👇 از کیبورد زیر استفاده کنید:"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

# --- دکمه‌های اصلی ---
@dp.message(F.text == "📢 کانال اطلاع‌رسانی")
async def channel_info(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="عضویت در کانال", url=CHANNEL_LINK)]])
    await message.answer("برای اطلاع از آفارها و برندگان روزانه وارد کانال شوید:", reply_markup=kb)

@dp.message(F.text == "👤 حساب کاربری")
async def user_profile(message: Message):
    _, balance, turnover, invited, _ = get_user(message.from_user.id)
    text = (
        f"👤 **حساب کاربری شما**\n\n"
        f"🆔 شناسه: `{message.from_user.id}`\n"
        f"💰 موجودی: {balance:,} تومان\n"
        f"🔄 گردش مالی باقی‌مانده جهت برداشت: {turnover:,} تومان\n"
        f"👥 تعداد دعوت‌ها: {invited} از {MAX_INVITES} نفر"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "👥 دعوت دوستان")
async def refer_friends(message: Message):
    _, _, _, invited, _ = get_user(message.from_user.id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start={message.from_user.id}"
    text = (
        f"🎁 **سیستم دعوت دوستان**\n\n"
        f"بابت هر دعوتی که انجام دهید مبلغ {INVITE_BONUS:,} تومان پاداش دریافت می‌کنید.\n"
        f"سقف دعوت: ۴ نفر (دعوت‌های شما: {invited}/{MAX_INVITES})\n\n"
        f"🔗 لینک اختصاصی شما:\n`{ref_link}`"
    )
    await message.answer(text, parse_mode="Markdown")

# --- بخش شارژ حساب ---
@dp.message(F.text == "💳 شارژ حساب")
async def deposit_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 کارت به کارت", callback_data="dep_card")],
        [InlineKeyboardButton(text="🎫 کد ووچر", callback_data="dep_voucher")],
        [InlineKeyboardButton(text="💎 ارز دیجیتال (TON)", callback_data="dep_ton")]
    ])
    await message.answer("لطفاً روش شارژ حساب را انتخاب کنید:", reply_markup=kb)

@dp.callback_query(F.data == "dep_card")
async def dep_card_callback(call: types.CallbackQuery, state: FSMContext):
    text = (
        f"📌 **شارژ از طریق کارت به کارت**\n\n"
        f"حداقل مبلغ شارژ: {MIN_CARD_DEPOSIT:,} تومان\n\n"
        f"💳 شماره کارت:\n`{CARD_NUMBER}`\n"
        f"👤 به نام: {CARD_HOLDER}\n\n"
        f"لطفاً پس از واریز، عکس رسید واریز را ارسال کنید:"
    )
    await call.message.answer(text, parse_mode="Markdown")
    await state.set_state(DepositState.waiting_for_card_receipt)
    await call.answer()

@dp.message(DepositState.waiting_for_card_receipt, F.photo)
async def process_card_receipt(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تأیید و شارژ", callback_data=f"approve_dep:{message.from_user.id}")],
        [InlineKeyboardButton(text="❌ رد درخواست", callback_data=f"reject_dep:{message.from_user.id}")]
    ])
    await bot.send_photo(
        ADMIN_ID,
        photo_id,
        caption=f"📥 **درخواست شارژ کارت به کارت**\nاز کاربر: `{message.from_user.id}`\nنام: {message.from_user.full_name}",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await message.answer("رسید شما ارسال شد. پس از بررسی توسط مدیریت، حساب شما شارژ خواهد شد.")
    await state.clear()

@dp.callback_query(F.data == "dep_voucher")
async def dep_voucher_callback(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer(f"🎫 حداقل مبلغ کد ووچر {MIN_VOUCHER_DEPOSIT:,} تومان می‌باشد.\nلطفاً کد ووچر خود را ارسال کنید:")
    await state.set_state(DepositState.waiting_for_voucher_code)
    await call.answer()

@dp.message(DepositState.waiting_for_voucher_code)
async def process_voucher_code(message: Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تأیید ووچر", callback_data=f"approve_dep:{message.from_user.id}")],
        [InlineKeyboardButton(text="❌ رد ووچر", callback_data=f"reject_dep:{message.from_user.id}")]
    ])
    await bot.send_message(
        ADMIN_ID,
        f"🎫 **کد ووچر دریافتی**\nاز کاربر: `{message.from_user.id}`\nکد: `{message.text}`",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await message.answer("کد ووچر ثبت شد و برای مدیریت ارسال گردید.")
    await state.clear()

@dp.callback_query(F.data == "dep_ton")
async def dep_ton_callback(call: types.CallbackQuery):
    text = (
        f"💎 **شارژ از طریق ارز دیجیتال (TON)**\n\n"
        f"آدرس ولت:\n`{TON_WALLET}`\n\n"
        f"پس از واریز، Hash تراکنش را برای پشتیبانی ارسال کنید."
    )
    await call.message.answer(text, parse_mode="Markdown")
    await call.answer()

# --- بخش مدیریت تأیید شارژ ---
@dp.callback_query(F.data.startswith("approve_dep:"))
async def admin_approve_dep(call: types.CallbackQuery, state: FSMContext):
    target_user_id = int(call.data.split(":")[1])
    await call.message.answer(f"لطفاً مبلغ شارژ به تومان را برای کاربر `{target_user_id}` وارد کنید:")
    await state.update_data(target_id=target_user_id)
    await state.set_state("waiting_admin_dep_amount")
    await call.answer()

@dp.message(F.state == "waiting_admin_dep_amount")
async def admin_set_dep_amount(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    target_id = data["target_id"]
    try:
        amount = int(message.text)
        update_balance(target_id, amount)
        add_required_turnover(target_id, amount) # قانون ۱۰۰٪ گردش مالی
        
        await bot.send_message(target_id, f"✅ حساب شما به مبلغ {amount:,} تومان شارژ شد.\nتوجه: جهت برداشت بایستی معادل این مبلغ بازی کنید.")
        await message.answer(f"حساب کاربر `{target_id}` با موفقیت شارژ شد.")
    except ValueError:
        await message.answer("لطفاً عدد معتبر وارد کنید.")
    await state.clear()

# --- بخش برداشت وجه ---
@dp.message(F.text == "🏧 برداشت وجه")
async def withdraw_start(message: Message, state: FSMContext):
    _, balance, turnover, _, _ = get_user(message.from_user.id)
    if turnover > 0:
        await message.answer(f"❌ امکان برداشت وجود ندارد.\nشما باید هنوز مبلغ {turnover:,} تومان دیگر شرط‌بندی کنید تا قفل برداشت باز شود.")
        return
    if balance <= 0:
        await message.answer("موجودی شما برای برداشت کافی نیست.")
        return
    
    await message.answer(f"💰 موجودی قابل برداشت: {balance:,} تومان\nمبلغ درخواستی برای برداشت را وارد کنید:")
    await state.set_state(WithdrawState.waiting_for_amount)

@dp.message(WithdrawState.waiting_for_amount)
async def withdraw_amount(message: Message, state: FSMContext):
    _, balance, turnover, _, _ = get_user(message.from_user.id)
    try:
        amount = int(message.text)
        if amount > balance or amount <= 0:
            await message.answer("مبلغ وارد شده معتبر نیست یا از موجودی شما بیشتر است.")
            return
        await state.update_data(w_amount=amount)
        await message.answer("شماره کارت و نام صاحب حساب جهت واریز را وارد کنید:")
        await state.set_state(WithdrawState.waiting_for_card_info)
    except ValueError:
        await message.answer("لطفاً یک عدد معتبر وارد کنید.")

@dp.message(WithdrawState.waiting_for_card_info)
async def withdraw_card_info(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data["w_amount"]
    user_id = message.from_user.id
    
    update_balance(user_id, -amount)
    
    await bot.send_message(
        ADMIN_ID,
        f"🏧 **درخواست برداشت جدید**\nکاربر: `{user_id}`\nمبلغ: {amount:,} تومان\nاطلاعات حساب:\n{message.text}",
        parse_mode="Markdown"
    )
    await message.answer("✅ درخواست برداشت شما ثبت شد و پس از بررسی واریز خواهد شد.")
    await state.clear()

# --- بخش بازی تاس ---
@dp.message(F.text == "🎲 بازی تاس")
async def play_dice_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="زوج (ضریب ۲)", callback_data="bet_type:even"), InlineKeyboardButton(text="فرد (ضریب ۲)", callback_data="bet_type:odd")],
        [InlineKeyboardButton(text="🎯 انتخاب عدد دقیق (ضریب ۶)", callback_data="bet_type:exact")]
    ])
    await message.answer("حالت شرط‌بندی را انتخاب کنید:", reply_markup=kb)

@dp.callback_query(F.data.startswith("bet_type:"))
async def bet_type_selected(call: types.CallbackQuery, state: FSMContext):
    b_type = call.data.split(":")[1]
    if b_type == "exact":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=str(i), callback_data=f"bet_num:{i}") for i in range(1, 4)],
            [InlineKeyboardButton(text=str(i), callback_data=f"bet_num:{i}") for i in range(4, 7)]
        ])
        await call.message.answer("عدد مورد نظر خود را انتخاب کنید (۱ تا ۶):", reply_markup=kb)
    else:
        await state.update_data(b_type=b_type, target_num=None)
        await call.message.answer("مبلغ شرط‌بندی (به تومان) را وارد کنید:")
        await state.set_state(BetState.waiting_for_amount)
    await call.answer()

@dp.callback_query(F.data.startswith("bet_num:"))
async def bet_num_selected(call: types.CallbackQuery, state: FSMContext):
    num = int(call.data.split(":")[1])
    await state.update_data(b_type="exact", target_num=num)
    await call.message.answer(f"عدد انتخاب شده: {num}\nمبلغ شرط‌بندی (به تومان) را وارد کنید:")
    await state.set_state(BetState.waiting_for_amount)
    await call.answer()

@dp.message(BetState.waiting_for_amount)
async def process_bet_amount(message: Message, state: FSMContext):
    user_id = message.from_user.id
    _, balance, _, _, _ = get_user(user_id)
    
    try:
        bet_amount = int(message.text)
        if bet_amount <= 0 or bet_amount > balance:
            await message.answer("موجودی شما کافی نیست یا مبلغ نامعتبر است.")
            return
        
        data = await state.get_data()
        b_type = data["b_type"]
        target_num = data.get("target_num")
        
        # کسر مبلغ شرط و به‌روزرسانی گردش مالی
        update_balance(user_id, -bet_amount)
        update_turnover(user_id, bet_amount)
        
        # پرتاب تاس اصلی تلگرام
        dice_msg = await message.answer_dice(emoji="🎲")
        dice_val = dice_msg.dice.value
        await asyncio.sleep(2.5) # صبر برای پایان انیمیشن تاس
        
        win = False
        multiplier = 0
        
        if b_type == "even" and dice_val % 2 == 0:
            win = True
            multiplier = 2
        elif b_type == "odd" and dice_val % 2 != 0:
            win = True
            multiplier = 2
        elif b_type == "exact" and dice_val == target_num:
            win = True
            multiplier = 6
            
        if win:
            prize = bet_amount * multiplier
            update_balance(user_id, prize)
            await message.answer(f"🎉 تبریک! عدد تاس {dice_val} آمد.\nشما برنده {prize:,} تومان شدید!")
        else:
            await message.answer(f"❌ متأسفانه عدد تاس {dice_val} آمد و شما باختید.")
            
        await state.clear()
    except ValueError:
        await message.answer("لطفاً یک عدد معتبر وارد کنید.")

# --- اجرای ربات ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
