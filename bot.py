import discord
from discord.ext import commands
from dotenv import load_dotenv          # ← new import
import os                               # ← new import
import requests
import html  # to fix weird characters like &quot;
import random
import asyncio

load_dotenv()                           # ← loads .env file
TOKEN = os.getenv('DISCORD_TOKEN')      # ← reads from env

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
active_quizzes = {}  # user_id -> {'questions': list, 'index': int, 'score': int, 'msg': message obj}

@bot.event
async def on_ready():
    print(f'Bot is online! Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

@bot.command()
async def hello(ctx):
    await ctx.send(f'Hi {ctx.author.mention}! I am your quiz bot 😊')

@bot.command(name='quiz')
async def start_quiz(ctx):
    # Removed category arg for now — always science
    user_id = ctx.author.id

    if user_id in active_quizzes:
        await ctx.send("You're already in a quiz! Finish it or wait.")
        return

    questions = []

    try:
        url = "https://opentdb.com/api.php?amount=5&category=17&difficulty=easy&type=multiple"
        print(f"Fetching science questions: {url}")

        response = requests.get(url, timeout=15)
        response.raise_for_status()  # Raise on HTTP errors like 429

        data = response.json()
        print(f"Response code: {data.get('response_code')}")

        if data.get('response_code') != 0:
            code = data.get('response_code')
            if code == 5:
                await ctx.send("Rate limit hit — wait 5–10 seconds and try again! ⏳")
            else:
                await ctx.send(f"API error code {code}. Try again later 😢")
            return

        questions = data['results']
        if not questions:
            await ctx.send("No questions available right now. Try again!")
            return

        print(f"Got {len(questions)} questions")

        # Clean HTML entities
        for q in questions:
            q['question'] = html.unescape(q['question'])
            q['correct_answer'] = html.unescape(q['correct_answer'])
            q['incorrect_answers'] = [html.unescape(a) for a in q['incorrect_answers']]

        # Shuffle answers
        for q in questions:
            answers = q['incorrect_answers'] + [q['correct_answer']]
            random.shuffle(answers)
            q['answers'] = answers
            q['correct_letter'] = chr(65 + answers.index(q['correct_answer']))  # A, B, C, D

        active_quizzes[user_id] = {
            'questions': questions,
            'index': 0,
            'score': 0,
            'original_channel': ctx.channel.id
        }

        await ctx.send(
            "Starting Science Quiz! 5 easy questions.\n"
            "React with 🇦 🇧 🇨 🇩 to answer (30 seconds per question).\n"
            "Type `!stopquiz` to quit early."
        )
        await send_next_question(ctx, user_id)

    except requests.exceptions.Timeout:
        await ctx.send("Trivia server timed out. Try again soon! ⏳")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            await ctx.send("Too many requests — wait 5–10 seconds and try again! ⏳")
        else:
            await ctx.send(f"HTTP error: {str(e)}. Try again!")
    except Exception as e:
        await ctx.send(f"Oops, error: {str(e)}")
        print(f"Error: {e}")

async def send_next_question(ctx, user_id):
    if user_id not in active_quizzes:
        return

    game = active_quizzes[user_id]
    idx = game['index']

    if idx >= len(game['questions']):
        final_msg = f"Quiz finished! 🎉\nYour score: **{game['score']}/{len(game['questions'])}**"
        await ctx.send(final_msg)
        del active_quizzes[user_id]
        return

    q = game['questions'][idx]

    embed = discord.Embed(
        title=f"Question {idx+1}/{len(game['questions'])}",
        description=q['question'],
        color=0x3498db
    )
    embed.add_field(name="A", value=q['answers'][0], inline=False)
    embed.add_field(name="B", value=q['answers'][1], inline=False)
    embed.add_field(name="C", value=q['answers'][2], inline=False)
    embed.add_field(name="D", value=q['answers'][3], inline=False)
    embed.set_footer(text="React with A/B/C/D in 30 seconds!")

    msg = await ctx.send(embed=embed)

    # Add reactions
    for letter in ['🇦', '🇧', '🇨', '🇩']:  # A B C D regional indicators
        await msg.add_reaction(letter)

    # Update game with current message
    game['current_msg'] = msg

    # Wait for reaction (simple timeout version)
    def check(reaction, user):
        return user.id == user_id and str(reaction.emoji) in ['🇦', '🇧', '🇨', '🇩'] and reaction.message.id == msg.id

    try:
        reaction, _ = await bot.wait_for('reaction_add', timeout=30.0, check=check)

        user_answer = {'🇦':'A', '🇧':'B', '🇨':'C', '🇩':'D'}[str(reaction.emoji)]

        if user_answer == q['correct_letter']:
            game['score'] += 1
            await ctx.send(f"✅ Correct! The answer was **{q['correct_letter']}. {q['correct_answer']}**")
        else:
            await ctx.send(f"❌ Wrong! The correct answer was **{q['correct_letter']}. {q['correct_answer']}**")

        game['index'] += 1
        await send_next_question(ctx, user_id)  # next question

    except asyncio.TimeoutError:
        await ctx.send(f"Time's up! The correct answer was **{q['correct_letter']}. {q['correct_answer']}**")
        game['index'] += 1
        await send_next_question(ctx, user_id)

# Stop command
@bot.command(name='stopquiz')
async def stop_quiz(ctx):
    user_id = ctx.author.id
    if user_id in active_quizzes:
        del active_quizzes[user_id]
        await ctx.send("Quiz stopped. You can start a new one with !quiz")
    else:
        await ctx.send("No active quiz to stop.")

bot.run(TOKEN)