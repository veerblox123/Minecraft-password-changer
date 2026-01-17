import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
from browser_automation import BrowserAutomation

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True 

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        self.tree.add_command(cpass_command)

bot = MyBot()

@app_commands.command(name="cpass", description="Bypass passkeys and sign in")
@app_commands.describe(email="Account email", password="Current password", new_password="New password")
async def cpass_command(interaction: discord.Interaction, email: str, password: str, new_password: str):
    await interaction.response.defer(ephemeral=True)
    automation = BrowserAutomation()
    
    try:
        await automation.start()
        await interaction.followup.send(f"🚀 Processing `{email}`...")
        
        success = await automation.login(email, password)
        
        if not success:
            if os.path.exists("login_error.png"):
                file = discord.File("login_error.png")
                await interaction.followup.send("❌ Login failed. See screenshot:", file=file)
            else:
                await interaction.followup.send("❌ Login failed. Passkey bypass failed.")
            return

        await interaction.followup.send("✅ Login successful! Browser is inside the account.")

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
    finally:
        await automation.close()

@bot.event
async def on_ready():
    print(f'✅ {bot.user} is online!')
    synced = await bot.tree.sync()
    print(f"🔄 Successfully synced {len(synced)} command(s).")

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))